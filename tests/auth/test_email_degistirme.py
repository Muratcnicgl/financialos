"""
P4.4 / BUG #215 — E-POSTA HİÇBİR YERDEN DEĞİŞTİRİLEMİYORDU.

İki ayrı sonuç doğuruyordu:

1. **Yanlış hukuki beyan.** `docs/legal/kvkk-consent-v2.md`: "verilerinizi uygulama
   üzerinden dilediğiniz an güncelleyebilirsiniz." E-posta için bu doğru DEĞİLDİ —
   `PUT /api/user` yalnız ad/saat dilimi/para birimi/locale güncelliyordu. KVKK 11/d
   düzeltme hakkı fiilen kullanılamıyordu.
2. **Kalıcı hesap kilidi.** Kayıtta adresini yanlış yazan kullanıcı (tek harf yeter):
   doğrulama postası gelmez → hesap etkinleşmez; şifre sıfırlayamaz; destek ona
   ulaşamaz; kendisi düzeltemez. Açık betada bu, sessizce kaybedilen kullanıcıdır.

Bu dosya düzeltmeyi kilitler VE düzeltmenin kendisinin yeni bir açık yaratmadığını
ispatlar: adres hemen değişmez (yanlış yazım öldürmez), çalınmış oturumla kaçırılamaz
(mevcut şifre şart), kullanıcı listesi sızmaz, eski bağlantı tekrar oynatılamaz.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.auth as auth_mod
from app import auth as _auth
from app.dependencies import get_db
from app.main import app
from app.models import Base, User

SIFRE = "Dogru-Sifre-123!"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-prod-0123456789")
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"):
        monkeypatch.delenv(k, raising=False)   # SMTP yok → dev token dönsün
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(name="a", email="eski@ornek.com",
               password_hash=_auth.hash_password(SIFRE), is_active=True))
    s.add(User(name="b", email="baskasi@ornek.com",
               password_hash=_auth.hash_password(SIFRE), is_active=True))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    auth_mod._RATE.clear()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _token(db, client) -> str:
    u = db.query(User).filter(User.email == "eski@ornek.com").first()
    return _auth.create_access_token(u.id, int(u.token_version or 0))


def _basliklar(db, client) -> dict:
    return {"Authorization": f"Bearer {_token(db, client)}"}


def _talep(client, db, yeni: str, sifre: str | None = SIFRE) -> "object":
    govde = {"new_email": yeni}
    if sifre is not None:
        govde["current_password"] = sifre
    return client.post("/api/auth/change-email", json=govde, headers=_basliklar(db, client))


# ── Hak fiilen kullanılabiliyor mu ──────────────────────────────────────────

def test_kvkk_duzeltme_hakki_uctan_uca_calisir(client, db):
    """Yanlış yazılmış adres DÜZELTİLEBİLMELİ — yoksa hesap kalıcı ölü."""
    r = _talep(client, db, "yeni@ornek.com")
    assert r.status_code == 200, r.text
    tok = r.json().get("_dev_token")
    assert tok, "Doğrulama token'ı üretilmedi"

    r2 = client.post("/api/auth/change-email-confirm", json={"token": tok})
    assert r2.status_code == 200, r2.text
    db.expire_all()
    u = db.query(User).filter(User.email == "yeni@ornek.com").first()
    assert u is not None, "E-posta güncellenmedi (düzeltme hakkı hâlâ kullanılamıyor)"
    assert u.email_verified_at is not None, "Yeni adres doğrulanmış sayılmadı"


def test_kvkk_metnindeki_vaat_kodda_karsiliksiz_degil():
    """L8 dersi: belgelenen ≠ ulaşılabilir. Metin 'güncelleyebilirsiniz' diyorsa yol OLMALI."""
    from pathlib import Path
    metin = Path("docs/legal/kvkk-consent-v2.md").read_text(encoding="utf-8")
    assert "Düzeltme" in metin
    yollar = [r.path for r in auth_mod.router.routes]
    assert "/api/auth/change-email" in yollar, \
        "KVKK metni düzeltme vaat ediyor ama kodda e-posta düzeltme ucu yok"


# ── Adres HEMEN değişmemeli (asıl bug'ın tekrarı) ───────────────────────────

def test_onaylanmadan_adres_degismez(client, db):
    """Yanlış yazım hesabı öldürmemeli: bağlantı tıklanmadan hiçbir şey değişmez."""
    _talep(client, db, "yanlis-yazim@ornek.com")
    db.expire_all()
    u = db.get(User, 1)
    assert u.email == "eski@ornek.com", "Adres onay beklemeden değişti (yanlış yazım = kilit)"


# ── Ele geçirme savunmaları ─────────────────────────────────────────────────

def test_sifresiz_talep_reddedilir(client, db):
    """Çalınmış oturumla adres kaçırılamamalı (hesap ele geçirme yolu)."""
    r = _talep(client, db, "saldirgan@ornek.com", sifre=None)
    assert r.status_code == 422, f"Şifresiz adres değiştirme kabul edildi: {r.status_code}"


def test_yanlis_sifre_reddedilir(client, db):
    r = _talep(client, db, "saldirgan@ornek.com", sifre="Yanlis-Sifre-999!")
    assert r.status_code == 401


def test_onayda_tum_oturumlar_duser(client, db):
    """Kimlik değişimi = oturum geçersizleme (şifre sıfırlamayla aynı çizgi, BUG #172)."""
    onceki = int(db.get(User, 1).token_version or 0)
    tok = _talep(client, db, "yeni@ornek.com").json()["_dev_token"]
    client.post("/api/auth/change-email-confirm", json={"token": tok})
    db.expire_all()
    assert int(db.get(User, 1).token_version or 0) > onceki, \
        "Adres değişti ama eski oturumlar yaşıyor (çalınmış token hâlâ geçerli)"


def test_baglanti_tek_kullanimlik(client, db):
    tok = _talep(client, db, "yeni@ornek.com").json()["_dev_token"]
    assert client.post("/api/auth/change-email-confirm", json={"token": tok}).status_code == 200
    r = client.post("/api/auth/change-email-confirm", json={"token": tok})
    assert r.status_code == 400, "Aynı bağlantı ikinci kez çalıştı"


def test_eski_baglanti_tekrar_oynatilamaz(client, db):
    """Bekleyen bağlantı varken adres değişirse eski bağlantı ÖLMELİ — yoksa hesap
    sahibinin haberi olmadan eski adrese geri döndürülebilir."""
    eski_tok = _talep(client, db, "birinci@ornek.com").json()["_dev_token"]
    ikinci = _talep(client, db, "ikinci@ornek.com").json()["_dev_token"]
    assert client.post("/api/auth/change-email-confirm", json={"token": ikinci}).status_code == 200
    r = client.post("/api/auth/change-email-confirm", json={"token": eski_tok})
    assert r.status_code == 400, "Eski bağlantı yeni adresin üzerine yazdı"


def test_gecersiz_token_reddedilir(client, db):
    assert client.post("/api/auth/change-email-confirm",
                       json={"token": "uydurma"}).status_code == 400


def test_sifre_sifirlama_tokeni_burada_gecmez(client, db):
    """Token tipi karışırsa bir akışın token'ı diğerini açar (tip doğrulaması şart)."""
    yanlis_tip = _auth.create_password_reset_token(1)
    assert client.post("/api/auth/change-email-confirm",
                       json={"token": yanlis_tip}).status_code == 400


# ── Enumerasyon ─────────────────────────────────────────────────────────────

def test_kayitli_adres_sizdirilmaz(client, db):
    """BUG #202 dersi: 'bu e-posta kayıtlı' yanıtı kullanıcı listesi sızdırır."""
    r_bos = _talep(client, db, "hic-kullanilmayan@ornek.com")
    r_dolu = _talep(client, db, "baskasi@ornek.com")
    assert r_dolu.status_code == r_bos.status_code == 200
    assert r_dolu.json()["message"] == r_bos.json()["message"], \
        "Yanıt farklı → adresin kayıtlı olduğu anlaşılıyor"
    assert "_dev_token" not in r_dolu.json(), "Başkasının adresi için token üretildi"


def test_baskasinin_adresi_ele_gecirilemez(client, db):
    _talep(client, db, "baskasi@ornek.com")
    db.expire_all()
    assert db.get(User, 1).email == "eski@ornek.com"
    assert db.get(User, 2).email == "baskasi@ornek.com", "Başkasının adresi çalındı"


def test_ayni_adres_reddedilir(client, db):
    r = _talep(client, db, "eski@ornek.com")
    assert r.status_code == 400


# ── Production'da token sızıntısı ───────────────────────────────────────────

def test_production_smtp_yoksa_token_donmez(client, db, monkeypatch):
    """BUG #170 dersi: SMTP yoksa prod'da token yanıtta dönerse tam hesap ele geçirme."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    r = _talep(client, db, "yeni@ornek.com")
    assert r.status_code == 200
    assert "_dev_token" not in r.json(), "Production yanıtında doğrulama token'ı var"


# ── SMTP açıkken: hangi adrese ne gidiyor ───────────────────────────────────

def test_dogrulama_YENI_adrese_bildirim_ESKI_adrese_gider(client, db, monkeypatch):
    """Doğrulama yeni adrese (kontrol kanıtı), bildirim eski adrese (kaçırma görünür olsun)."""
    gonderilenler: list[tuple[str, str]] = []
    monkeypatch.setattr(auth_mod, "smtp_configured", lambda: True)
    monkeypatch.setattr(auth_mod, "send_email_change_verification",
                        lambda adres, link: gonderilenler.append(("dogrulama", adres)))
    monkeypatch.setattr(auth_mod, "send_email_changed_notice",
                        lambda adres, maskeli: gonderilenler.append(("bildirim", adres)))

    _talep(client, db, "yeni@ornek.com")
    assert ("dogrulama", "yeni@ornek.com") in gonderilenler, \
        "Doğrulama yeni adrese gitmedi (yanlış yazım tespit edilemez)"

    tok = _auth.create_email_change_token(1, "yeni@ornek.com", "eski@ornek.com")
    assert client.post("/api/auth/change-email-confirm", json={"token": tok}).status_code == 200
    assert ("bildirim", "eski@ornek.com") in gonderilenler, \
        "Eski adrese uyarı gitmedi — sessiz hesap kaçırma görünmez kalır"
