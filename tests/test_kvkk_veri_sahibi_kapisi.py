"""
BUG #243 (denetim D26 + D27 + D28) — KVKK VERİ-SAHİBİ HAKLARI (export + silme) ŞEMADAN TÜRETİLİR.

Üç bulgu, tek kök: "tüm verin" ve "tüm verin silinir" taahhütleri **elle bakılan listelere**
dayanıyordu; şema büyüdükçe listeler geride kaldı ve kimse fark etmedi.

- **D26:** export kullanıcının **bcrypt şifre hash'ini** ve **OAuth kimliğini** dosyaya
  döküyordu (`_row_to_dict` / `_row` TÜM kolonları basıyor). Bu dosya tasarımı gereği
  kullanıcının diskine iner, e-postayla paylaşılır, buluta yedeklenir — kimlik doğrulama
  sırrı taşınabilirlik hakkının kapsamında DEĞİLDİR.
- **D27:** hesap silindikten sonra kullanıcının **e-posta adresi ve operatörün kişi hakkında
  yazdığı serbest not** `beta_invites`'ta kalıyordu (`purge` yalnız `user_id` kolonu olan
  tablolara bakıyordu; oradaki kolon `used_by_user_id`). "Tüm veriniz kalıcı olarak silinir"
  taahhüdü fiilen yanlıştı.
- **D28:** UI'nin ve KVKK metninin gösterdiği uç (`/api/users/me/export`) `goal_allocations`
  ve `goal_rules`'u hiç dökmüyordu; tamlık testi ise DİĞER ucu (`/api/user/export`) ölçüyordu
  — yeşil test yanlış fonksiyonu doğruluyordu (kapsam yanılsaması).

Kapı bu yüzden ŞEMAYI gezer: `app/data_subject.py` kaydında sınıflandırılmamış bir tablo
kalamaz (yeni tablo eklendiğinde süit kırılır), export iki uçta AYNI şeyi döner, ve silme
sonrası kullanıcının e-postası veritabanının HİÇBİR metin kolonunda kalamaz.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, Transaction, TransactionType, Goal,
    GoalAllocation, GoalRule, BetaInvite, ErrorLog,
)
from app.data_subject import KAYIT, disa_aktar, GIZLENEN_ALANLAR
from app.kvkk import purge_user_data

EPOSTA = "silinecek@example.com"


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(eng, "connect")
    def _fk(dbapi_con, _):
        dbapi_con.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def kullanici(db_session):
    u = User(id=1, name="Test", email=EPOSTA,
             password_hash="$2b$12$ORNEKHASHDEGERIABCDEFGHIJKLMNOP",
             oauth_provider="google", oauth_sub="1187766554433")
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def veri(db_session, kullanici):
    """Hedef katkısı + kuralı + davet kaydı olan gerçekçi bir kullanıcı."""
    acc = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=1000)
    txn = Transaction(user_id=1, transaction_type=TransactionType.income, amount=100,
                      transaction_date=date(2026, 8, 1))
    db_session.add_all([acc, txn]); db_session.commit()
    g = Goal(user_id=1, goal_type="savings", title="Hedef", target_amount=5000)
    db_session.add(g); db_session.commit()
    db_session.add_all([
        GoalAllocation(goal_id=g.id, transaction_id=txn.id, amount=50.0),
        GoalRule(goal_id=g.id, name="kural", criteria="{}", allocation_type="fixed",
                 allocation_value=10),
        BetaInvite(code="ABC123", email=EPOSTA, note="tanıdık — iş arkadaşı",
                   used_by_user_id=1, used_at=datetime.utcnow(),
                   created_at=datetime.utcnow()),
        ErrorLog(fingerprint="x", error_type="E", message="m", path="/p",
                 last_user_id=1, first_seen_at=datetime.utcnow(), last_seen_at=datetime.utcnow()),
    ])
    db_session.commit()
    return g


@pytest.fixture
def client(db_session, kullanici):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ============================================================
# 1. KAYIT ŞEMAYI TAM KAPSAR (yeni tablo sessizce dışarıda kalamaz)
# ============================================================

def test_her_tablo_kayitta_siniflandirilmis():
    eksik = sorted({t.name for t in Base.metadata.sorted_tables} - set(KAYIT))
    assert not eksik, (
        f"Bu tablolar KVKK kaydında sınıflandırılmamış: {eksik}. Her tablo ya kullanıcı "
        "verisidir (export + silme) ya da gerekçeli olarak kullanıcı-dışıdır."
    )


def test_kayitta_semada_olmayan_tablo_yok():
    fazla = sorted(set(KAYIT) - {t.name for t in Base.metadata.sorted_tables})
    assert not fazla, f"Kayıtta şemada olmayan tablo var (bayat kayıt): {fazla}"


def test_kapsam_tabani_kullanici_verisi_tablolari():
    kullanici_verisi = [ad for ad, k in KAYIT.items() if k.disa_aktarilir]
    assert len(kullanici_verisi) >= 18, (
        f"Yalnız {len(kullanici_verisi)} tablo kullanıcı verisi sayılıyor — kayıt bozulmuş "
        "olabilir, kapı kör kalır"
    )


def test_her_kullanici_disi_tablonun_gerekcesi_var():
    gerekcesiz = [ad for ad, k in KAYIT.items()
                  if not k.disa_aktarilir and not (k.gerekce or "").strip()]
    assert not gerekcesiz, f"Gerekçesiz 'kullanıcı verisi değil' sınıflandırması: {gerekcesiz}"


def test_sir_gorunumlu_her_kolon_siniflandirilmis():
    """Yeni bir `*_hash` / `*_token` / `*_secret` kolonu eklendiğinde, export'a girip
    girmeyeceği KARARI verilmiş olmalı. Otomatik desen-gizleme yapılmıyor: `tokens_in`
    (LLM kullanım sayacı) kullanıcının kendi verisidir, gizlenmesi taşınabilirliği baltalar
    — bu yüzden karar listeye YAZILIR, tahmin edilmez (L26)."""
    import re as _re
    from app.data_subject import SIR_GORUNUMLU_AMA_KULLANICI_VERISI
    desen = _re.compile(r"password|hash|secret|token|api_key|_sub$", _re.I)
    siniflandirilmis = GIZLENEN_ALANLAR | SIR_GORUNUMLU_AMA_KULLANICI_VERISI
    bulunan, eksik = [], []
    for tablo in Base.metadata.sorted_tables:
        if not KAYIT[tablo.name].disa_aktarilir:
            continue
        for kolon in tablo.c:
            if desen.search(kolon.name):
                bulunan.append(f"{tablo.name}.{kolon.name}")
                if kolon.name not in siniflandirilmis:
                    eksik.append(f"{tablo.name}.{kolon.name}")
    assert len(bulunan) >= 4, f"Sır-görünümlü kolon taraması bozuk (bulunan={bulunan})"
    assert not eksik, (
        f"Bu kolonlar sır GİBİ görünüyor ama export kararı verilmemiş: {eksik}. "
        "GIZLENEN_ALANLAR'a (dışarıda kalır) ya da SIR_GORUNUMLU_AMA_KULLANICI_VERISI'ne "
        "(kullanıcının kendi verisi) yaz."
    )


# ============================================================
# 2. EXPORT — tam (D28) ve sırsız (D26)
# ============================================================

def test_export_hedef_katki_ve_kurallarini_icerir(db_session, kullanici, veri):
    veriler = disa_aktar(db_session, kullanici)
    assert len(veriler["goal_allocations"]) == 1, "Hedef katkı geçmişi export'ta yok (D28)"
    assert len(veriler["goal_rules"]) == 1, "Otomatik tahsis kuralları export'ta yok (D28)"


@pytest.mark.parametrize("uc", ["/api/user/export", "/api/users/me/export"])
def test_export_kimlik_dogrulama_sirlarini_dokmez(client, veri, uc):
    r = client.get(uc)
    assert r.status_code == 200
    govde = r.json()
    for alan in GIZLENEN_ALANLAR:
        assert alan not in govde["user"], f"{uc} '{alan}' alanını dosyaya döküyor (D26)"
    assert "$2b$" not in r.text, f"{uc} yanıtında bcrypt hash izi var"
    assert "1187766554433" not in r.text, f"{uc} yanıtında OAuth kimliği var"


@pytest.mark.parametrize("uc", ["/api/user/export", "/api/users/me/export"])
def test_export_kullanicinin_kendi_verisini_yine_de_verir(client, veri, uc):
    """Gizleme, taşınabilirliği baltalamamalı (L6: kapı ürünü kıramaz)."""
    govde = client.get(uc).json()
    assert govde["user"]["email"] == EPOSTA
    assert govde["accounts"] and govde["transactions"] and govde["goals"]


def test_iki_export_ucu_ayni_kapsami_doner(client, veri):
    """D28'in kökü: iki ayrı export uygulaması ayrışmıştı (biri iki tabloyu atlıyordu)."""
    a = set(client.get("/api/user/export").json())
    b = set(client.get("/api/users/me/export").json())
    assert a == b, f"İki export ucu farklı kapsam dönüyor: yalnız-A={a-b}, yalnız-B={b-a}"


def test_export_kayitla_tutarli(client, veri):
    """Kayıtta 'dışa aktarılır' denen her tablo yanıtta bir anahtar olmalı."""
    govde = client.get("/api/users/me/export").json()
    eksik = [k.disa_aktarma_anahtari for k in KAYIT.values()
             if k.disa_aktarilir and k.disa_aktarma_anahtari not in govde]
    assert not eksik, f"Kayıt bunları vaat ediyor ama export dönmüyor: {eksik}"


# ============================================================
# 3. SİLME — hiçbir tabloda iz kalmaz (D27)
# ============================================================

def _eposta_gecen_tablolar(db) -> dict[str, list]:
    """Şema-geneli tarama: hangi tablonun hangi metin kolonunda e-posta duruyor."""
    kalanlar: dict[str, list] = {}
    for tablo in Base.metadata.sorted_tables:
        metin_kolonlari = [c for c in tablo.c
                           if isinstance(getattr(c.type, "python_type", None), type)
                           and c.type.python_type is str]
        if not metin_kolonlari:
            continue
        for satir in db.execute(select(tablo)).mappings():
            for c in metin_kolonlari:
                if satir.get(c.name) and EPOSTA in str(satir[c.name]):
                    kalanlar.setdefault(tablo.name, []).append(c.name)
    return kalanlar


def test_silme_oncesi_tarama_epostayi_bulur(db_session, kullanici, veri):
    """Meta-test: tarama çalışmıyorsa alttaki kapı sessizce yeşil kalır (L23)."""
    bulunan = _eposta_gecen_tablolar(db_session)
    assert "users" in bulunan and "beta_invites" in bulunan, (
        f"Tarama silme ÖNCESİ bile e-postayı bulamıyor: {bulunan}"
    )


def test_silme_sonrasi_hicbir_tabloda_eposta_kalmaz(db_session, kullanici, veri):
    purge_user_data(db_session, 1)
    db_session.commit()
    kalan = _eposta_gecen_tablolar(db_session)
    assert not kalan, (
        f"Silme sonrası kullanıcının e-postası şu tablolarda duruyor: {kalan}. "
        "KVKK m.7 + rıza metnindeki 'tüm veriniz kalıcı olarak silinir' taahhüdü."
    )


def test_silme_operator_notunu_da_temizler(db_session, kullanici, veri):
    """Not, kişi hakkında operatörün yazdığı İLİŞKİ bilgisidir — kişisel veridir."""
    purge_user_data(db_session, 1)
    db_session.commit()
    davet = db_session.query(BetaInvite).first()
    assert davet is not None, "Davet KAYDI silinmemeli (kod tüketimi işletme kaydıdır)"
    assert davet.email is None and davet.note is None and davet.used_by_user_id is None, (
        f"Davet satırında kişisel iz kaldı: email={davet.email!r} note={davet.note!r} "
        f"used_by={davet.used_by_user_id!r}"
    )
    assert davet.used_at is not None, "Kodun kullanıldığı bilgisi korunmalı (davet tekrar kullanılamaz)"


def test_silme_hata_kaydindaki_kullanici_atfini_kaldirir(db_session, kullanici, veri):
    purge_user_data(db_session, 1)
    db_session.commit()
    hata = db_session.query(ErrorLog).first()
    assert hata is not None, "Hata kaydı operatörün teşhis verisidir, silinmez"
    assert hata.last_user_id is None, "Silinen kullanıcıya atıf kaldı"
