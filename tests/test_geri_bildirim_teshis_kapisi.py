"""
B2 / BUG #281 — GERİ BİLDİRİM TEŞHİS EDİLEBİLİR OLMALI.

Premis düzeltmesi (11 Ağu 2026): kapalı beta charter'ının taslağı "geri bildirim sistemi
diskte yok, sıfırdan yazılacak" diyordu; ölçüm çürüttü — FEAT-033 var (model + migration
+ uç + widget + `scripts/beta_triage.py` operatör aracı + 6 test). Eksik olan SİSTEM
değil, TEŞHİS EDİLEBİLİRLİKTİ: kayıt "kim, ne zaman, hangi sekme, ne yazdı" diyordu ama
**"hangi kod koşuyordu ve o an ne patladı"** demiyordu. Teşhis edilemeyen geri bildirim
gürültüdür.

Kilitlenen dört sözleşme:
  1. **Alan kümesi SABİTTİR.** Yeni alan eklemek gizlilik kapısından geçer — bu test yeni
     alan eklendiğinde kırmızıya döner (sessiz genişleme yok).
  2. **Sürüm SUNUCUDAN türetilir**, istemcinin beyanı değil (bayat sekme yanlış sürüm
     bildirir ve yanlışlık sessiz olur).
  3. **Ham User-Agent SAKLANMAZ** — yalnız tarayıcı ailesi (parmak izi yüzeyi, KVKK).
  4. **Zincir uçtan uca:** 5xx → korelasyon kimliği → geri bildirim kaydı aynı kodu taşır.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Feedback
from app.routers.feedback import tarayici_ailesi, FeedbackCreate

_PATLAYAN_UC = "/api/meta/durum"


def _patlayan_db():
    raise RuntimeError("bilerek patlatildi")


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════
# 1. Alan kümesi SABİT (gizlilik sınırı)
# ══════════════════════════════════════════════════════════════════════

# Kayda giren her sütun ve NEDEN gerektiği. Yeni alan eklenirse buraya da yazılmalı —
# yazılmazsa kapı kırmızıya döner. Bu liste "muafiyet" değil, GİZLİLİK BEYANIDIR ve
# B5'teki KVKK metnine birebir yansır.
BEKLENEN_ALANLAR: dict[str, str] = {
    "id": "birincil anahtar",
    "user_id": "kim gönderdi (kendi kayıtlarını görebilsin)",
    "workspace_id": "aktif workspace (M40 / ADR-036 izolasyon)",
    "kind": "sikayet | istek | oneri | kafa_karistirdi",
    "message": "kullanıcının YAZDIĞI metin — tek serbest alan",
    "page": "hangi ekrandan gönderildi",
    "status": "new | reviewed (operatör triyajı)",
    "created_at": "ne zaman",
    "app_version": "hangi kod koşuyordu — SUNUCUDAN türetilir",
    "istek_id": "kullanıcının gördüğü korelasyon kimliği (BUG #280)",
    "viewport_w": "ekran genişliği — telefon/masaüstü ayrımı (L29'un veri tarafı)",
    "tarayici": "tarayıcı AİLESİ (ham UA değil — parmak izi yüzeyi)",
    "pwa": "ana ekrana eklenmiş uygulamadan mı",
}


def test_kayda_giren_alan_kumesi_sabittir(db):
    """Yeni alan eklendiğinde bu kapı kırmızıya döner: gizlilik sınırı sessizce genişlemez."""
    gercek = {s["name"] for s in sa_inspect(db.get_bind()).get_columns("feedback")}
    beklenen = set(BEKLENEN_ALANLAR)
    assert gercek == beklenen, (
        f"feedback alan kümesi değişti.\n  Yeni: {sorted(gercek - beklenen)}\n"
        f"  Kayıp: {sorted(beklenen - gercek)}\n"
        "Yeni alan gizlilik kapısından geçer: BEKLENEN_ALANLAR'a gerekçesiyle yaz ve "
        "KVKK metnine (B5) yansıt."
    )


def test_istemci_ekran_goruntusu_veya_tutar_alani_YOK():
    """Bağlayıcı sınır: otomatik ekran görüntüsü yok, işlem/tutar otomatik kopyalanmaz."""
    yasak_izler = ("screenshot", "ekran_goruntusu", "amount", "tutar", "balance", "bakiye")
    for alan in BEKLENEN_ALANLAR:
        assert not any(iz in alan.lower() for iz in yasak_izler), (
            f"Gizlilik sınırını ihlal eden alan: {alan}"
        )


def test_kullaniciya_donen_alanlar_dar(client):
    """Tarayıcı/viewport operatör içindir; kullanıcıya geri yansıtmak yüzeyi genişletir."""
    r = client.post("/api/feedback", json={"kind": "oneri", "message": "test"})
    assert r.status_code == 201
    assert set(r.json()) == {"id", "kind", "message", "page", "status", "created_at",
                             "app_version", "istek_id"}


# ══════════════════════════════════════════════════════════════════════
# 2. Sürüm sunucudan, tarayıcı aileden
# ══════════════════════════════════════════════════════════════════════

def test_surum_SUNUCUDAN_turetilir_istemci_beyani_degil(client, db):
    """İstemci sürüm gönderemez; gönderse bile dikkate alınmaz."""
    from app.version import full_version
    r = client.post("/api/feedback",
                    json={"kind": "sikayet", "message": "x", "app_version": "SAHTE-9.9.9"})
    assert r.status_code == 201
    kayit = db.query(Feedback).first()
    assert kayit.app_version == full_version()[:40]
    assert "SAHTE" not in (kayit.app_version or "")


def test_surum_elle_yazilmamis_gercek_kaynaktan_gelir(client, db):
    """Sabit string yazılsaydı deploy sonrası sessizce bayatlardı."""
    from app import version as _v
    r = client.post("/api/feedback", json={"kind": "oneri", "message": "x"})
    assert r.status_code == 201
    assert _v.APP_VERSION in db.query(Feedback).first().app_version


@pytest.mark.parametrize("ua,beklenen", [
    ("Mozilla/5.0 (Windows) AppleWebKit Chrome/120 Safari/537", "Chrome"),
    ("Mozilla/5.0 (Windows) Chrome/120 Safari/537 Edg/120", "Edge"),
    ("Mozilla/5.0 (Linux) Chrome/120 Safari/537 OPR/106", "Opera"),
    ("Mozilla/5.0 (Android) Chrome/120 SamsungBrowser/23 Safari/537", "Samsung"),
    ("Mozilla/5.0 (Macintosh) Firefox/121", "Firefox"),
    ("Mozilla/5.0 (iPhone) AppleWebKit Version/17 Safari/605", "Safari"),
    ("kim-bilir-ne/1.0", "diger"),
    (None, None),
    ("", None),
])
def test_tarayici_ailesi_ozelden_genele_cozulur(ua, beklenen):
    """Edge/Opera kendini Chrome, Chrome kendini Safari diye tanıtır — sıra yanlışsa
    herkes Safari görünür ve ölçüm sessizce yanlış olur."""
    assert tarayici_ailesi(ua) == beklenen


def test_ham_user_agent_SAKLANMAZ(client, db):
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) Safari/605.1.15"
    r = client.post("/api/feedback", json={"kind": "oneri", "message": "x"},
                    headers={"User-Agent": ua})
    assert r.status_code == 201
    kayit = db.query(Feedback).first()
    assert kayit.tarayici == "Safari"
    hepsi = " ".join(str(getattr(kayit, a) or "") for a in BEKLENEN_ALANLAR)
    assert "iPhone OS 17_2" not in hepsi, "Ham UA kaydedilmiş (parmak izi yüzeyi)"


# ══════════════════════════════════════════════════════════════════════
# 3. Korelasyon kimliği: temizleyici TEK KAYNAK
# ══════════════════════════════════════════════════════════════════════

def test_istemciden_gelen_kimlik_dogrudan_yazilmaz(client, db):
    """Aynı temizleyici (correlation.gelen_id_temizle) — ikinci kopya yok (L46)."""
    r = client.post("/api/feedback",
                    json={"kind": "sikayet", "message": "x", "istek_id": "satir\nsonu"})
    assert r.status_code in (201, 422)
    if r.status_code == 201:
        assert db.query(Feedback).first().istek_id is None


def test_gecerli_kimlik_kaydedilir(client, db):
    r = client.post("/api/feedback",
                    json={"kind": "sikayet", "message": "x", "istek_id": "abc23xyz"})
    assert r.status_code == 201
    assert db.query(Feedback).first().istek_id == "abc23xyz"


def test_kafa_karistirdi_turu_kabul_edilir(client, db):
    """Dördüncü tür: hata değil, istek değil — kullanılabilirlik sinyali."""
    r = client.post("/api/feedback", json={"kind": "kafa_karistirdi", "message": "anlamadım"})
    assert r.status_code == 201
    assert db.query(Feedback).first().kind == "kafa_karistirdi"


def test_eski_uc_tur_korunur(client):
    """Geçmişe dönük eşleme borcu üretilmedi."""
    for tur in ("sikayet", "istek", "oneri"):
        assert client.post("/api/feedback", json={"kind": tur, "message": "x"}).status_code == 201


def test_tanimsiz_tur_reddedilir(client):
    assert client.post("/api/feedback", json={"kind": "uydurma", "message": "x"}).status_code == 422


def test_pydantic_tur_kumesi_ile_model_yorumu_ayrismaz():
    """Şemadaki tür kümesi ile testteki beyan aynı kaynaktan doğrulanır (drift kilidi)."""
    import typing
    alan = FeedbackCreate.model_fields["kind"]
    turler = set(typing.get_args(alan.annotation))
    assert turler == {"sikayet", "istek", "oneri", "kafa_karistirdi"}


# ══════════════════════════════════════════════════════════════════════
# 4. Uçtan uca zincir: 5xx → kimlik → geri bildirim
# ══════════════════════════════════════════════════════════════════════

def test_5xx_kimligi_geri_bildirime_baglanir(db, monkeypatch):
    """Kullanıcının yaşadığı zincirin tamamı: hata al → kodu gör → o kodla bildir."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-b2-teshis-0123456789abcdef")
    monkeypatch.setattr("app.database.SessionLocal", sessionmaker(bind=db.get_bind()))

    # 1) Kullanıcı bir hata alır ve ekranda bir kod görür.
    app.dependency_overrides[get_db] = _patlayan_db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    hatali = TestClient(app, raise_server_exceptions=False)
    r = hatali.get(_PATLAYAN_UC)
    assert r.status_code == 500
    kod = r.json()["istek_id"]
    app.dependency_overrides.clear()

    # 2) Aynı kodla geri bildirim gönderir.
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    saglikli = TestClient(app)
    r2 = saglikli.post("/api/feedback",
                       json={"kind": "sikayet", "message": "koç açılmadı",
                             "page": "coach", "istek_id": kod})
    assert r2.status_code == 201
    app.dependency_overrides.clear()

    # 3) Operatör kaydı bulur — kod, sürüm ve ekran bağlamı yerinde.
    kayit = db.query(Feedback).first()
    assert kayit.istek_id == kod, "Zincir koptu: bildirilen kod kayda düşmedi"
    assert kayit.app_version, "Hangi kod koşuyordu bilinmiyor"
    assert kayit.page == "coach"
