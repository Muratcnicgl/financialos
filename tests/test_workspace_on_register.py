"""
M62 (ADR-037) — register/oauth personal workspace + ws_id fail-fast.

Personal workspace yaratımı artık register/oauth akışına KODA bağlı (elle script değil).
Production'da personal workspace yoksa active_workspace_id fail-fast.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base, User, Workspace, WorkspaceMembership, WorkspaceRole
from app.services.workspace_setup import ensure_personal_workspace


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-workspace-register-0123456789")
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# --- ensure_personal_workspace (birim) ---

def test_ensure_idempotent(db):
    u = User(name="a")
    db.add(u); db.commit()
    ws1 = ensure_personal_workspace(db, u)
    ws2 = ensure_personal_workspace(db, u)  # ikinci çağrı yeni yaratmaz
    assert ws1.id == ws2.id
    assert db.query(Workspace).filter_by(owner_user_id=u.id).count() == 1
    m = db.query(WorkspaceMembership).filter_by(workspace_id=ws1.id, user_id=u.id).one()
    assert m.role == WorkspaceRole.owner and ws1.is_personal is True


# --- register akışı ---

def test_register_personal_workspace_yaratir(client, db):
    r = client.post("/api/auth/register", json={
        "email": "yeni@x.com", "password": "guclu-sifre-123", "kvkk_consent": True})
    assert r.status_code == 201, r.text
    u = db.query(User).filter_by(email="yeni@x.com").one()
    ws = db.query(Workspace).filter_by(owner_user_id=u.id, is_personal=True).one()
    assert db.query(WorkspaceMembership).filter_by(workspace_id=ws.id, user_id=u.id).count() == 1


# --- fail-fast (prod) ---

def test_active_workspace_prod_fail_fast(client, db, monkeypatch):
    """Production + personal workspace YOK → 500 (sessiz sızma yerine görünür hata)."""
    # workspace'siz user + geçerli token
    from app import auth as _auth
    u = User(name="nows", email="nows@x.com", is_active=True)
    db.add(u); db.commit()
    token = _auth.create_access_token(u.id)
    monkeypatch.setenv("ENVIRONMENT", "production")
    r = client.get("/api/accounts", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 500
    assert "personal workspace" in r.json()["detail"]


def test_active_workspace_dev_none_legacy(client, db, monkeypatch):
    """Development + personal workspace YOK → 200 (legacy user_id yolu, warning)."""
    from app import auth as _auth
    u = User(name="nows2", email="nows2@x.com", is_active=True)
    db.add(u); db.commit()
    token = _auth.create_access_token(u.id)
    monkeypatch.delenv("ENVIRONMENT", raising=False)  # development
    r = client.get("/api/accounts", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200  # legacy yol, kilitlenmez
