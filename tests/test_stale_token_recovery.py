"""
M61 (BUG #158) — Stale-token kurtarma (backend tarafı).

Kök defect: `get_current_user` token varken invalid/expired olunca AUTH_ENABLED'a
bakmadan koşulsuz 401 atıyordu → lokal (auth kapalı) kurulumda ölü token TÜM uygulamayı
kilitliyordu (17 Tem Murat'ı kilitledi). Fix: auth kapalıyken bozuk token yok sayılıp
fallback'e düşülür; auth açıkken 401 + makine-okunur `code`.
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

BAD_TOKEN = "eyJhbGciOiJIUzI1NiJ9.bozuk.imza-gecersiz"


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(name="murat"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_bozuk_token_auth_kapali_fallbacke_duser(client, monkeypatch):
    """BUG #158: AUTH_ENABLED kapalı + çürük token → 401 DEĞİL, fallback (ilk user) → 200."""
    monkeypatch.delenv("AUTH_ENABLED", raising=False)  # kapalı (default)
    r = client.get("/api/cockpit", headers={"Authorization": f"Bearer {BAD_TOKEN}"})
    assert r.status_code == 200, f"çürük token uygulamayı kilitledi: {r.status_code}"


def test_bozuk_token_auth_acik_401_token_expired(client, monkeypatch):
    """AUTH_ENABLED açık + çürük token → 401 + code=token_expired (frontend ayırt etsin)."""
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-stale-token-0123456789abcd")
    r = client.get("/api/cockpit", headers={"Authorization": f"Bearer {BAD_TOKEN}"})
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["code"] == "token_expired"


def test_tokensiz_auth_acik_401_auth_required(client, monkeypatch):
    """AUTH_ENABLED açık + token yok → 401 + code=auth_required."""
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-stale-token-0123456789abcd")
    r = client.get("/api/cockpit")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "auth_required"


def test_tokensiz_auth_kapali_fallback(client, monkeypatch):
    """AUTH_ENABLED kapalı + token yok → fallback → 200 (mevcut davranış korunur)."""
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    r = client.get("/api/cockpit")
    assert r.status_code == 200
