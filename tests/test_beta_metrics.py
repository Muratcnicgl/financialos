"""
P7/P8 — BUG #214: operatör betanın KULLANILIP kullanılmadığını göremiyordu.

`beta_triage` yalnız ŞİKÂYET EDENİ gösterir. Beta'nın en olası başarısızlığı gürültülü
çöküş değil, SESSİZ TERK'tir: 8 kişi davet edilir, 6'sı kayıt olur, 5'i ilk ekranda
takılır, hiçbiri şikâyet etmez — panelde her şey yeşil görünür, ürün ölüdür. P8'in
çıkış ölçütü ("gerçek kullanıcı davranışıyla sınanmış operasyon") bu yüzden ölçülemezdi.

Bu dosya iki şeyi birlikte kilitler:
1. Metrik DOĞRU sayıyor (yanlış metrik, metrik olmamasından beterdir — yanlış güven verir).
2. Metrik KİMLİK SIZDIRMIYOR. Kullanım ölçmek için mahremiyeti satmak gerekmez; çıktıda
   e-posta, isim, serbest metin ve PARA TUTARI bulunması testle YASAKTIR.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import scripts.beta_metrics as bm
from app.models import (
    Account,
    AccountType,
    ApiCallLog,
    ApiCallStatus,
    Base,
    CoachMemory,
    ErrorLog,
    Feedback,
    MasterCheckpoint,
    CheckpointType,
    Transaction,
    TransactionType,
    User,
)

SIMDI = datetime.utcnow()
DUN = SIMDI - timedelta(days=1)


@pytest.fixture
def db(monkeypatch):
    """3 kullanıcılı gerçekçi beta: biri kullanıyor, biri takıldı, biri hiç dönmedi."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    s = Session()

    kullanan = User(name="a", email="ali.veli@example.com", created_at=SIMDI - timedelta(days=5),
                    email_verified_at=SIMDI)
    takilan = User(name="b", email="ayse.yilmaz@example.com", created_at=SIMDI - timedelta(days=3))
    hayalet = User(name="c", email="hic@example.com", created_at=SIMDI - timedelta(days=2))
    s.add_all([kullanan, takilan, hayalet])
    s.commit()

    # KULLANAN: hesap + işlem + koç, İKİ ayrı günde (tutunma sayılmalı)
    s.add_all([
        Account(user_id=kullanan.id, name="Kasa", account_type=AccountType.cash),
        Transaction(user_id=kullanan.id, transaction_type=TransactionType.expense,
                    amount=1234.56, created_at=DUN, description="gizli market fisi"),
        ApiCallLog(user_id=kullanan.id, provider="gemini", model="m",
                   status=ApiCallStatus.success, duration_ms=900, tool_calls_count=0,
                   called_at=SIMDI),
        ApiCallLog(user_id=kullanan.id, provider="gemini", model="m",
                   status=ApiCallStatus.failed, duration_ms=10, tool_calls_count=0,
                   called_at=SIMDI),
        CoachMemory(user_id=kullanan.id, role="user", content="gizli koc mesaji",
                    timestamp=SIMDI),
        MasterCheckpoint(user_id=kullanan.id, title="Kural", description="d",
                         checkpoint_type=CheckpointType.red_line),
    ])
    # TAKILAN: yalnız hesap açtı, kayıt gününde — iz var ama tek gün
    s.add(Account(user_id=takilan.id, name="Kart", account_type=AccountType.credit_card))
    s.add(Transaction(user_id=takilan.id, transaction_type=TransactionType.income,
                      amount=100, created_at=takilan.created_at))
    # HAYALET: hiçbir iz yok
    s.add_all([
        Feedback(user_id=takilan.id, kind="sikayet", message="cok gizli sikayet metni",
                 status="new", created_at=SIMDI),
        ErrorLog(fingerprint="f1", error_type="RuntimeError", message="patladi",
                 path="/api/x", method="GET", occurrence_count=4,
                 first_seen_at=DUN, last_seen_at=SIMDI),
    ])
    s.commit()
    monkeypatch.setattr(bm, "SessionLocal", Session)
    yield s
    s.close()


# ── Doğruluk ────────────────────────────────────────────────────────────────

def test_huni_takilan_kullaniciyi_gosterir(db):
    h = bm.topla(db)["huni"]
    assert h["kayitli"] == 3
    assert h["hesap_ekleyen"] == 2, "Hesap açan kullanıcı sayısı yanlış"
    assert h["koc_kullanan"] == 1, "Koçu kullanan yalnız 1 kişi olmalı"
    assert h["kendi_kuralini_yazan"] == 1


def test_sessiz_terk_gorunur(db):
    """Asıl kör nokta: hiç iz bırakmadan giden kullanıcı sayılabilmeli."""
    m = bm.topla(db)
    assert m["hic_iz_birakmayan"] == 1, "Sessizce terk eden kullanıcı görünmüyor"


def test_ayni_gun_coklu_sinyal_tek_sayilir(db):
    """Bir kişinin yoğun günü 'çok kullanıcı' gibi görünmemeli."""
    m = bm.topla(db)
    assert m["aktif"]["bugun"] == 1, f"Aynı gün iki sinyal şişirdi: {m['aktif']}"


def test_tutunma_tek_gun_ile_donen_ayrilir(db):
    t = bm.topla(db)["tutunma"]
    assert t["geri_donen"] == 1, "Başka bir gün dönen kullanıcı sayılmadı"
    assert t["tek_gun_kalan"] == 1, "İlk gün bırakan kullanıcı ayrılmadı"


def test_koc_hata_orani(db):
    k = bm.topla(db)["koc"]
    assert k["cagri"] == 2 and k["basarisiz"] == 1
    assert k["hata_orani_yuzde"] == 50.0
    assert k["ortalama_sure_ms"] == 900, "Başarısız çağrı süre ortalamasını kirletiyor"


def test_saglik_ozeti(db):
    s = bm.topla(db)["saglik"]
    assert s["acik_geri_bildirim"] == 1
    assert s["hata_grubu"] == 1 and s["hata_tekrari"] == 4


def test_bos_veritabaninda_cokmez(monkeypatch):
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    monkeypatch.setattr(bm, "SessionLocal", Session)
    assert bm.main([]) == 0, "Sıfır kullanıcıda araç çöküyor (ilk gün kullanılamaz)"


# ── Gizlilik kilidi ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("argv", [[], ["--json"]])
def test_cikti_kimlik_sizdirmaz(db, capsys, argv):
    """Kullanım ölçmek için mahremiyeti satmak gerekmez — çıktı yalnız sayı olmalı."""
    assert bm.main(argv) == 0
    cikti = capsys.readouterr().out
    yasak = [
        "ali.veli@example.com", "ayse.yilmaz", "@example.com",   # e-posta
        "gizli market fisi", "gizli koc mesaji", "cok gizli",     # serbest metin
        "1234.56", "1234,56",                                     # para tutarı
    ]
    for iz in yasak:
        assert iz not in cikti, f"Metrik çıktısında kişisel veri var: {iz!r}"


def test_json_ciktisi_yalniz_sayi_icerir(db):
    """Makine okunur çıktı da aynı sözü vermeli (cron/izleme buradan besleniyor)."""
    m = bm.topla(db)

    def _gez(dugum):
        if isinstance(dugum, dict):
            for k, v in dugum.items():
                assert isinstance(k, str)
                _gez(v)
        elif isinstance(dugum, list):
            for v in dugum:
                _gez(v)
        else:
            assert isinstance(dugum, (int, float)), \
                f"Metrik ağacında sayı olmayan değer var: {dugum!r}"

    _gez(m)
