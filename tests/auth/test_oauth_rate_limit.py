"""
M36 (Wave-4, ADR-033) — OAuth endpoint rate-limit + auth-gerektirmez regresyon kilidi.

CHARTER REVIZE (charter-revise-w4-1): Wave-4 charter M36 "M21 OAuth regression fix"
premise'i YANLIŞ çıktı. R3 (14 Tem 2026) canlı doğrulama:
  curl /api/auth/oauth/google/login  ->  HTTP 307 -> accounts.google.com  (401 DEĞİL)
Kod tarafında oauth_login (auth.py:210) ve oauth_callback (auth.py:227) hiçbir
`Depends(get_current_user)` içermez — sadece `_rate_limit(request, "oauth")`. Yani
M21 rate_limit eklenmesi OAuth'u bozmadı; regression hiç var olmadı.

Bu test var-olmayan regression'ı KOVALAMAK yerine gerçek boşluğu kapatır: OAuth
bucket'ının 10/dk limiti + login endpoint'inin auth GEREKTİRMEDİĞİ (401 asla) —
gelecekte yanlışlıkla `require_auth` eklenirse bu test kırmızıya döner.
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
import app.routers.auth as auth_mod
import app.services.oauth as oauth_mod
from app.rate_limit import limit_for


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-prod-0123456789")
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "gid.apps.googleusercontent.com")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "GOCSPX-secret")
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_ID", "Ov23liXXXX")
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_SECRET", "ghsecret")


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
    auth_mod._RATE.clear()
    oauth_mod._states.clear()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
    auth_mod._RATE.clear()


def test_oauth_bucket_10_per_dakika():
    """M36: OAuth bucket production değeri 10/60s (charter spesifikasyonu)."""
    assert limit_for("oauth") == (10, 60)


def test_oauth_login_auth_gerektirmez_asla_401(client):
    """M36 R3 kilidi: OAuth login endpoint'i auth GEREKTİRMEZ — 307 döner, asla 401.

    Regression premise'i (401 'Not authenticated') YANLIŞTI. Bu assertion gelecekte
    yanlışlıkla Depends(get_current_user)/require_auth eklenirse kırmızıya döner.
    """
    r = client.get("/api/auth/oauth/google/login", follow_redirects=False)
    assert r.status_code == 307, f"OAuth login auth gerektiriyor gibi ({r.status_code})"
    assert r.status_code != 401
    assert r.headers["location"].startswith("https://accounts.google.com/")


def test_oauth_login_10_gecer_11_429(client):
    """M36: OAuth bucket 10/dk — 10 istek 307, 11. istek 429 (auth 401 değil)."""
    for i in range(10):
        r = client.get("/api/auth/oauth/google/login", follow_redirects=False)
        assert r.status_code == 307, f"{i}. istek 307 değil: {r.status_code}"
    r11 = client.get("/api/auth/oauth/google/login", follow_redirects=False)
    assert r11.status_code == 429
    assert "Çok fazla" in r11.json()["detail"]


def test_oauth_callback_auth_gerektirmez(client, monkeypatch):
    """M36: callback endpoint'i de auth gerektirmez — geçersiz state 400 (401 değil)."""
    monkeypatch.setattr(auth_mod._oauth, "exchange_code", lambda p, c: {})
    r = client.get("/api/auth/callback/google?code=abc&state=SAHTE", follow_redirects=False)
    assert r.status_code == 400  # state hatası, auth 401 DEĞİL
    assert r.status_code != 401
