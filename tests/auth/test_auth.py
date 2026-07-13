"""
M11 (ADR-033) — Auth + Multi-user + KVKK testleri.

AUTH_ENABLED=1 + SECRET_KEY ile JWT yolu; in-memory DB; get_db override.
Kapsam: register (KVKK zorunlu, dup email), login (hatalı şifre, enumeration),
refresh, logout (blacklist), me, data segregation (token→user), KVKK sil, rate-limit.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base, User, RevokedToken
import app.routers.auth as auth_mod


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    """Auth env'ini YALNIZ bu modül testlerinde ayarla (global sızıntı yok — test izolasyonu).

    monkeypatch teardown'da otomatik geri alır; diğer testlerin tek-kullanıcı fallback'i
    (AUTH_ENABLED yok) korunur.
    """
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-prod-0123456789")
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("AUTH_RATE_MAX", "5")
    monkeypatch.setenv("AUTH_RATE_WINDOW", "60")


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    auth_mod._RATE.clear()  # rate-limit sıfırla (testler arası izolasyon)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _register(client, email="a@x.com", password="parola123", consent=True):
    return client.post("/api/auth/register", json={
        "email": email, "password": password, "name": "A", "kvkk_consent": consent,
    })


# --- Register ---

def test_register_basarili_token_doner(client):
    r = _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_register_kvkk_zorunlu(client):
    r = _register(client, consent=False)
    assert r.status_code == 422


def test_register_dup_email_409(client):
    _register(client)
    r = _register(client)
    assert r.status_code == 409


def test_register_kisa_sifre_422(client):
    r = client.post("/api/auth/register", json={
        "email": "b@x.com", "password": "short", "kvkk_consent": True})
    assert r.status_code == 422


# --- Login ---

def test_login_basarili(client):
    _register(client)
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "parola123"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_yanlis_sifre_401(client):
    _register(client)
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "yanlis"})
    assert r.status_code == 401


def test_login_olmayan_kullanici_401(client):
    r = client.post("/api/auth/login", json={"email": "yok@x.com", "password": "parola123"})
    assert r.status_code == 401


# --- Me (JWT doğrulama) ---

def test_me_token_ile(client):
    tok = _register(client).json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["email"] == "a@x.com"


def test_me_tokensiz_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_gecersiz_token_401(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage.token.xyz"})
    assert r.status_code == 401


# --- Refresh / Logout ---

def test_refresh_yeni_access(client):
    rt = _register(client).json()["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_logout_sonrasi_refresh_gecersiz(client, db_session):
    rt = _register(client).json()["refresh_token"]
    assert client.post("/api/auth/logout", json={"refresh_token": rt}).status_code == 204
    # Blacklist'e yazıldı
    assert db_session.query(RevokedToken).count() == 1
    # Artık refresh çalışmamalı
    r = client.post("/api/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 401


def test_access_token_refresh_olarak_reddedilir(client):
    at = _register(client).json()["access_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": at})
    assert r.status_code == 401  # type mismatch


# --- Data segregation (token → doğru user) ---

def test_data_segregation_iki_kullanici(client):
    ta = _register(client, email="a@x.com").json()["access_token"]
    tb = _register(client, email="b@x.com").json()["access_token"]
    ra = client.get("/api/auth/me", headers={"Authorization": f"Bearer {ta}"})
    rb = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tb}"})
    assert ra.json()["email"] == "a@x.com"
    assert rb.json()["email"] == "b@x.com"
    assert ra.json()["id"] != rb.json()["id"]


# --- KVKK sil ---

def test_kvkk_delete_kullaniciyi_siler(client, db_session):
    tok = _register(client).json()["access_token"]
    assert db_session.query(User).count() == 1
    r = client.delete("/api/users/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 204
    assert db_session.query(User).count() == 0
    # Silinen kullanıcının token'ı artık geçersiz
    r2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 401


def test_kvkk_export_veri_doner(client):
    tok = _register(client).json()["access_token"]
    r = client.get("/api/users/me/export", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "a@x.com"
    assert "exported_at" in body


# --- Rate limit (W3-041, brute-force) ---

def test_rate_limit_login(client):
    _register(client)
    # AUTH_RATE_MAX=5 → 5 login sonrası 6. istek 429
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "a@x.com", "password": "yanlis"})
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "parola123"})
    assert r.status_code == 429
