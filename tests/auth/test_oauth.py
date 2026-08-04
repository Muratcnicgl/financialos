"""
M11 (ADR-033) — OAuth (Google/GitHub) akış testleri.

Gerçek sağlayıcı çağrısı yapılmaz (exchange_code mock). login redirect, state CSRF,
callback'te user create/login + JWT + frontend redirect test edilir.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base, User
import app.routers.auth as auth_mod
import app.services.oauth as oauth_mod


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


# --- login redirect ---

def test_google_login_307_redirect(client):
    r = client.get("/api/auth/oauth/google/login", follow_redirects=False)
    assert r.status_code == 307
    loc = r.headers["location"]
    assert loc.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "state=" in loc and "client_id=" in loc
    assert "redirect_uri=http" in loc


def test_github_login_307_redirect(client):
    r = client.get("/api/auth/oauth/github/login", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"].startswith("https://github.com/login/oauth/authorize")


def test_bilinmeyen_provider_404(client):
    r = client.get("/api/auth/oauth/apple/login", follow_redirects=False)
    assert r.status_code == 404


def test_yapilandirilmamis_provider_501(client, monkeypatch):
    monkeypatch.delenv("OAUTH_GOOGLE_CLIENT_ID", raising=False)
    r = client.get("/api/auth/oauth/google/login", follow_redirects=False)
    assert r.status_code == 501


# --- callback ---

def _valid_state():
    return oauth_mod.new_state()


def test_callback_yeni_kullanici_olusturur(client, db_session, monkeypatch):
    monkeypatch.setattr(auth_mod._oauth, "exchange_code",
                        lambda p, c: {"provider": "google", "sub": "G1", "email": "yeni@x.com", "name": "Yeni"})
    st = _valid_state()
    r = client.get(f"/api/auth/callback/google?code=abc&state={st}", follow_redirects=False)
    assert r.status_code == 307
    # BUG #179 (P2): token'lar ARTIK URL'de taşınmaz — tek-kullanımlık değişim kodu döner
    # (tarayıcı geçmişi/access log/Referer sızıntısı kapandı).
    loc = r.headers["location"]
    assert loc.startswith("http://localhost:5173/auth/oauth-success?code=")
    assert "access_token=" not in loc and "refresh_token=" not in loc
    u = db_session.query(User).filter(User.email == "yeni@x.com").first()
    assert u is not None and u.oauth_provider == "google" and u.oauth_sub == "G1"
    assert u.password_hash is None and u.kvkk_consent_at is not None


def test_callback_mevcut_kullaniciya_baglar(client, db_session, monkeypatch):
    # Email/şifreyle kayıtlı kullanıcı OAuth ile girince hesabı bağlanır
    db_session.add(User(email="var@x.com", name="Var", password_hash="x", is_active=True))
    db_session.commit()
    monkeypatch.setattr(auth_mod._oauth, "exchange_code",
                        lambda p, c: {"provider": "github", "sub": "H9", "email": "var@x.com", "name": "Var"})
    st = _valid_state()
    r = client.get(f"/api/auth/callback/github?code=abc&state={st}", follow_redirects=False)
    assert r.status_code == 307
    u = db_session.query(User).filter(User.email == "var@x.com").first()
    assert u.oauth_provider == "github" and u.oauth_sub == "H9"
    assert u.password_hash == "x"  # mevcut şifre korunur


def test_callback_gecersiz_state_400(client, monkeypatch):
    monkeypatch.setattr(auth_mod._oauth, "exchange_code", lambda p, c: {})
    r = client.get("/api/auth/callback/google?code=abc&state=SAHTE", follow_redirects=False)
    assert r.status_code == 400


def test_callback_eksik_code_400(client):
    st = _valid_state()
    r = client.get(f"/api/auth/callback/google?state={st}", follow_redirects=False)
    assert r.status_code == 400


def test_callback_exchange_hatasi_400(client, monkeypatch):
    def _boom(p, c):
        raise ValueError("token alınamadı")
    monkeypatch.setattr(auth_mod._oauth, "exchange_code", _boom)
    st = _valid_state()
    r = client.get(f"/api/auth/callback/google?code=bad&state={st}", follow_redirects=False)
    assert r.status_code == 400


# --- state tek kullanımlık ---

def test_state_tek_kullanimlik():
    s = oauth_mod.new_state()
    assert oauth_mod.consume_state(s) is True
    assert oauth_mod.consume_state(s) is False
