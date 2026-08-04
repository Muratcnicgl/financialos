"""
P8 (Wave-9) — BUG #202: açık kayıtta e-posta ENUMERASYONU + sahte hesap spam'i.

`POST /api/auth/register` var olan bir e-posta için 409 "Bu e-posta zaten kayıtlı"
dönüyordu → saldırgan e-posta listesini sürerek **kimlerin kullanıcı olduğunu** öğrenir
(KVKK açısından müşteri listesi sızıntısı; hedefli oltalama için değerli). Ayrıca
doğrulamasız kayıt, sahte adreslerle hesap açmayı serbest bırakır.

Kapalı betada (davetli-only) bu risk sınırlıydı: enumerasyon için geçerli davet kodu
gerekiyordu. **Açık betaya (P8) geçişte** gerçek çözüm şart: kayıt HER DURUMDA aynı
yanıtı döner ve hesap ancak e-postadaki bağlantıyla etkinleşir.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth as _auth
from app.main import app
from app.dependencies import get_db
from app.models import Base, User


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-email-verify-0123456789abcdef")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("REGISTRATION_MODE", "open")     # açık beta senaryosu
    monkeypatch.setenv("REQUIRE_EMAIL_VERIFICATION", "1")  # açık beta = doğrulama açık
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(k, raising=False)
    from app import rate_limit
    rate_limit.reset()


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _kayit(client, email="a@example.com"):
    return client.post("/api/auth/register", json={
        "email": email, "password": "Guclu-Parola-2026!", "name": "A", "kvkk_consent": True})


def test_production_acik_kayitta_dogrulama_zorunlu(monkeypatch):
    """Varsayılan (env ezmesi olmadan): PRODUCTION + açık kayıt → doğrulama şart."""
    monkeypatch.delenv("REQUIRE_EMAIL_VERIFICATION", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REGISTRATION_MODE", "open")
    from app.beta_access import email_verification_required
    assert email_verification_required() is True


def test_developmentta_zorunlu_degil(monkeypatch):
    """SMTP'siz yerel geliştirmede kayıt akışı KİLİTLENMEZ."""
    monkeypatch.delenv("REQUIRE_EMAIL_VERIFICATION", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("REGISTRATION_MODE", "open")
    from app.beta_access import email_verification_required
    assert email_verification_required() is False


def test_davetli_modda_dogrulama_gerekmez(monkeypatch):
    """Kapalı betada kayıt zaten operatör kontrolünde — akış ağırlaştırılmaz."""
    monkeypatch.delenv("REQUIRE_EMAIL_VERIFICATION", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    from app.beta_access import email_verification_required
    assert email_verification_required() is False


def test_kayit_token_vermez_hesap_pasif(client, db):
    r = _kayit(client)
    assert r.status_code == 201
    assert "access_token" not in r.json(), "Doğrulanmadan token verildi"
    u = db.query(User).first()
    assert u.is_active is False and u.email_verified_at is None


def test_dogrulanmamis_hesapla_giris_yapilamaz(client):
    _kayit(client)
    r = client.post("/api/auth/login", json={"email": "a@example.com",
                                             "password": "Guclu-Parola-2026!"})
    assert r.status_code == 401


def test_enumerasyon_kapali(client, db):
    """ASIL KAPI: var olan ve olmayan e-posta AYNI yanıtı almalı."""
    r1 = _kayit(client, "ayni@example.com")
    r2 = _kayit(client, "ayni@example.com")     # ikinci kez — kayıtlı
    r3 = _kayit(client, "baska@example.com")    # hiç kayıtlı değil
    assert r1.status_code == r2.status_code == r3.status_code, (
        f"Durum kodları farklı: {r1.status_code}/{r2.status_code}/{r3.status_code}"
    )
    assert r1.json() == r2.json() == r3.json(), "Yanıt gövdeleri kullanıcı varlığını sızdırıyor"
    assert db.query(User).filter(User.email == "ayni@example.com").count() == 1


def test_dogrulama_baglantisi_hesabi_etkinlestirir(client, db):
    _kayit(client)
    u = db.query(User).first()
    token = _auth.create_email_verification_token(u.id)

    r = client.get(f"/api/auth/verify-email?token={token}")
    assert r.status_code == 200, r.text[:200]
    db.refresh(u)
    assert u.is_active is True and u.email_verified_at is not None

    r = client.post("/api/auth/login", json={"email": "a@example.com",
                                             "password": "Guclu-Parola-2026!"})
    assert r.status_code == 200, "Doğrulamadan sonra giriş çalışmıyor"


def test_dogrulama_baglantisi_tek_kullanimlik(client, db):
    _kayit(client)
    u = db.query(User).first()
    token = _auth.create_email_verification_token(u.id)
    assert client.get(f"/api/auth/verify-email?token={token}").status_code == 200
    assert client.get(f"/api/auth/verify-email?token={token}").status_code == 400


def test_gecersiz_dogrulama_tokeni_reddedilir(client):
    assert client.get("/api/auth/verify-email?token=uydurma").status_code == 400


def test_baska_tur_token_dogrulama_icin_kullanilamaz(client, db):
    _kayit(client)
    u = db.query(User).first()
    sahte = _auth.create_access_token(u.id)
    assert client.get(f"/api/auth/verify-email?token={sahte}").status_code == 400


def test_davetli_modda_eski_akis_korunur(client, monkeypatch, db):
    """Regresyon: kapalı betada kayıt anında token verir (davet zaten kontrol)."""
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    monkeypatch.delenv("REQUIRE_EMAIL_VERIFICATION", raising=False)
    from app.beta_access import davet_olustur
    d = davet_olustur(db)
    r = client.post("/api/auth/register", json={
        "email": "davetli@example.com", "password": "Guclu-Parola-2026!",
        "name": "D", "kvkk_consent": True, "invite_code": d.code})
    assert r.status_code == 201 and r.json().get("access_token")
