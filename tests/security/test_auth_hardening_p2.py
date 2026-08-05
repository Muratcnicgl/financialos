"""
P2 (Wave-9 publish yolu) — kimlik/oturum sertleştirme kapıları.

Kapalı-beta denetiminde doğrulanan üç KRİTİK açık:

  BUG #170 — `POST /api/auth/password-reset-request` SMTP yapılandırılmamışsa geçerli
             sıfırlama token'ını HTTP YANITINDA düz metin döndürüyordu; koşulda
             `is_production()` YOKTU. Prod'da SMTP eksik/bozuksa herhangi biri, herhangi
             bir e-posta için token alıp şifreyi değiştirebilirdi (tam hesap ele geçirme).
             Ayrıca token'ın dönüp dönmemesi kullanıcı-enumerasyonu sızdırıyordu.

  BUG #171 — `validate_security_config` yalnız SECRET_KEY'e bakıyordu. `AUTH_ENABLED`
             varsayılanı KAPALI olduğundan `ENVIRONMENT=production` + AUTH_ENABLED unset
             ile deploy edilen instance TÜM API'yi kimliksiz "ilk kullanıcı"ya açıyordu.
             (compose dosyası set ediyor; systemd/manuel/PaaS yolunda koruma yoktu.)

  BUG #172 — Şifre sıfırlandığında mevcut oturumlar geçerli kalıyordu: çalınmış 30 günlük
             refresh token, kurban şifresini değiştirdikten SONRA da çalışıyordu. Ayrıca
             sıfırlama token'ı tek kullanımlık değildi ve logout access token'ı iptal etmiyordu.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-p2-auth-hardening-0123456789abcdef")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    # SMTP tanımsız bırakılır (dev-token dalını sınamak için)
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


@pytest.fixture
def kayitli(client):
    r = client.post("/api/auth/register", json={
        "email": "kurban@example.com", "password": "Eski-Parola-2026!",
        "name": "Kurban", "kvkk_consent": True})
    assert r.status_code == 201, r.text[:200]
    return r.json()


# ── BUG #170: prod'da sıfırlama token'ı yanıtta DÖNMEZ ───────────────────────

def test_production_da_dev_token_donmez(client, kayitli, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    r = client.post("/api/auth/password-reset-request", json={"email": "kurban@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert "_dev_token" not in body, (
        "PRODUCTION'da sıfırlama token'ı HTTP yanıtında döndü — hesap ele geçirme açığı"
    )


def test_production_da_yanit_enumerasyon_sizdirmaz(client, kayitli, monkeypatch):
    """Kayıtlı ve kayıtsız e-posta AYNI yanıtı almalı (kullanıcı listesi sızmasın)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    r1 = client.post("/api/auth/password-reset-request", json={"email": "kurban@example.com"})
    r2 = client.post("/api/auth/password-reset-request", json={"email": "yok@example.com"})
    assert r1.json() == r2.json(), "Kayıtlı/kayıtsız e-posta yanıtları farklı — enumerasyon"


def test_dev_ortaminda_kolaylik_korunur(client, kayitli):
    """Regresyon: dev'de (SMTP yokken) token dönmeye devam eder — geliştirme kolaylığı."""
    r = client.post("/api/auth/password-reset-request", json={"email": "kurban@example.com"})
    assert "_dev_token" in r.json()


# ── BUG #171: production'da AUTH_ENABLED zorunlu ─────────────────────────────

def test_production_auth_kapaliysa_fail_fast(monkeypatch):
    """BUG #227 (D06) sonrası: 'unutmak' artık kapatmıyor; AÇIKÇA kapatmak prod'da yasak."""
    from app.settings import validate_security_config
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "yeterince-uzun-ve-guclu-bir-secret-key-0123456789")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    with pytest.raises(RuntimeError, match="AUTH_ENABLED"):
        validate_security_config()


def test_production_auth_degiskeni_unutulursa_acik_kalir(monkeypatch):
    """BUG #227: değişken hiç yazılmamışsa kimlik doğrulama AÇIK sayılır (fail-closed)."""
    from app.settings import validate_security_config
    from app import auth as _auth
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "yeterince-uzun-ve-guclu-bir-secret-key-0123456789")
    monkeypatch.setenv("SUPPORT_EMAIL", "destek@ornek-urun.com")
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    assert _auth.auth_enabled() is True
    validate_security_config()  # açık sayıldığı için fail-fast tetiklenmez


def test_production_auth_acikken_gecer(monkeypatch):
    from app.settings import validate_security_config
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "yeterince-uzun-ve-guclu-bir-secret-key-0123456789")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    # BUG #210 (P8): production destek kanalı da şart — bu test AUTH kapısını ölçer.
    monkeypatch.setenv("SUPPORT_EMAIL", "destek@ornek-urun.com")
    validate_security_config()  # hata fırlatmamalı


def test_dev_ortaminda_auth_kapali_olabilir(monkeypatch):
    """Regresyon: yerel/tek-kullanıcı kurulum AUTH'suz çalışmaya devam eder.

    BUG #227: kapatma artık AÇIKÇA yapılır (`AUTH_ENABLED=false`) — dev'de hâlâ mümkün."""
    from app.settings import validate_security_config
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("SECRET_KEY", "yeterince-uzun-ve-guclu-bir-secret-key-0123456789")
    validate_security_config()


# ── BUG #172: şifre sıfırlama tüm oturumları düşürür ─────────────────────────

def _reset_token(client) -> str:
    r = client.post("/api/auth/password-reset-request", json={"email": "kurban@example.com"})
    return r.json()["_dev_token"]


def test_sifre_sifirlaninca_eski_refresh_gecersiz(client, kayitli):
    """Çalınan refresh token, kurban şifresini sıfırlayınca ÇALIŞMAMALI."""
    calinan_refresh = kayitli["refresh_token"]

    token = _reset_token(client)
    r = client.post("/api/auth/password-reset-confirm",
                    json={"token": token, "new_password": "Yeni-Parola-2026!"})
    assert r.status_code == 200, r.text[:200]

    r = client.post("/api/auth/refresh", json={"refresh_token": calinan_refresh})
    assert r.status_code == 401, (
        f"Şifre sıfırlandıktan sonra ESKİ refresh token hâlâ çalışıyor ({r.status_code}) — "
        "saldırgan hesapta kalmaya devam eder"
    )


def test_sifre_sifirlaninca_eski_access_gecersiz(client, kayitli):
    calinan_access = {"Authorization": f"Bearer {kayitli['access_token']}"}
    token = _reset_token(client)
    client.post("/api/auth/password-reset-confirm",
                json={"token": token, "new_password": "Yeni-Parola-2026!"})

    r = client.get("/api/cockpit", headers=calinan_access)
    assert r.status_code == 401, (
        f"Şifre sıfırlandıktan sonra eski access token çalışıyor ({r.status_code})"
    )


def test_sifirlama_tokeni_tek_kullanimlik(client, kayitli):
    """Aynı sıfırlama token'ı ikinci kez kullanılamamalı (posta kutusu/geçmiş sızıntısı)."""
    token = _reset_token(client)
    r1 = client.post("/api/auth/password-reset-confirm",
                     json={"token": token, "new_password": "Yeni-Parola-2026!"})
    assert r1.status_code == 200
    r2 = client.post("/api/auth/password-reset-confirm",
                     json={"token": token, "new_password": "Saldirgan-Parolasi-2026!"})
    assert r2.status_code == 400, f"Sıfırlama token'ı ikinci kez kullanılabildi ({r2.status_code})"


def test_yeni_parola_ile_giris_calisir(client, kayitli):
    """Pozitif kontrol: sertleştirme normal akışı bozmuyor."""
    token = _reset_token(client)
    client.post("/api/auth/password-reset-confirm",
                json={"token": token, "new_password": "Yeni-Parola-2026!"})
    r = client.post("/api/auth/login",
                    json={"email": "kurban@example.com", "password": "Yeni-Parola-2026!"})
    assert r.status_code == 200, r.text[:200]
    yeni_access = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/cockpit", headers=yeni_access).status_code == 200


def test_logout_access_tokeni_da_iptal_eder(client, kayitli):
    """BUG #172 (c): logout'tan sonra ELDEKİ access token da çalışmamalı."""
    access = {"Authorization": f"Bearer {kayitli['access_token']}"}
    assert client.get("/api/cockpit", headers=access).status_code == 200

    r = client.post("/api/auth/logout", json={"refresh_token": kayitli["refresh_token"]},
                    headers=access)
    assert r.status_code == 204

    r = client.get("/api/cockpit", headers=access)
    assert r.status_code == 401, (
        f"Logout sonrası access token hâlâ geçerli ({r.status_code}) — ortak bilgisayarda risk"
    )
