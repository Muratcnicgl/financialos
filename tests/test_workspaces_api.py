"""
M41 (ADR-036) — Workspace CRUD + izin endpoint testleri.

get_db + get_current_user override ile çok-kullanıcı izin senaryoları (in-memory).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Workspace, WorkspaceMembership, WorkspaceRole


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def users(db):
    u1 = User(name="murat")
    u2 = User(name="es")
    db.add_all([u1, u2])
    db.commit()
    # u1'in personal workspace'i + owner membership
    ws = Workspace(owner_user_id=u1.id, name="Murat (Kişisel)", is_personal=True)
    db.add(ws)
    db.commit()
    db.add(WorkspaceMembership(workspace_id=ws.id, user_id=u1.id, role=WorkspaceRole.owner))
    db.commit()
    return u1, u2, ws


@pytest.fixture
def client(db, users):
    app.dependency_overrides[get_db] = lambda: db
    state = {"user": users[0]}
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    c = TestClient(app)
    c._active_user = state  # testler aktif user'ı değiştirebilsin (starlette _state ile çakışmaz)
    yield c
    app.dependency_overrides.clear()


def _as(client, user):
    client._active_user["user"] = user


def test_list_workspaces_kendi_uyeliklerini_doner(client, users):
    u1, u2, ws = users
    r = client.get("/api/workspaces")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1 and body[0]["id"] == ws.id
    assert body[0]["role"] == "owner" and body[0]["is_personal"] is True


def test_create_workspace_owner_yapar(client, users):
    r = client.post("/api/workspaces", json={"name": "Aile"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Aile" and body["role"] == "owner" and body["is_personal"] is False


def test_get_workspace_uye_olmayan_403(client, db, users):
    u1, u2, ws = users
    _as(client, u2)  # u2 ws'nin üyesi değil
    r = client.get(f"/api/workspaces/{ws.id}")
    assert r.status_code == 403


def test_get_workspace_uye_detay_gorur(client, users):
    u1, u2, ws = users
    r = client.get(f"/api/workspaces/{ws.id}")
    assert r.status_code == 200
    assert r.json()["members"][0]["user_id"] == u1.id


def test_remove_member_viewer_403(client, db, users):
    # u1 paylaşımlı workspace yaratır, u2'yi viewer ekler; u2 üye çıkarmayı deneyince 403
    r = client.post("/api/workspaces", json={"name": "Aile"})
    wsid = r.json()["id"]
    u1, u2, _ = users
    db.add(WorkspaceMembership(workspace_id=wsid, user_id=u2.id, role=WorkspaceRole.viewer))
    db.commit()
    _as(client, u2)
    r = client.request("DELETE", f"/api/workspaces/{wsid}/members/{u1.id}",
                       headers={"X-Workspace-Id": str(wsid)})
    assert r.status_code == 403


def test_remove_member_owner_yapar(client, db, users):
    r = client.post("/api/workspaces", json={"name": "Aile"})
    wsid = r.json()["id"]
    u1, u2, _ = users
    db.add(WorkspaceMembership(workspace_id=wsid, user_id=u2.id, role=WorkspaceRole.viewer))
    db.commit()
    # owner u1 aktif
    r = client.request("DELETE", f"/api/workspaces/{wsid}/members/{u2.id}",
                       headers={"X-Workspace-Id": str(wsid)})
    assert r.status_code == 204
    assert db.query(WorkspaceMembership).filter_by(workspace_id=wsid, user_id=u2.id).first() is None


def test_remove_owner_yasak(client, db, users):
    r = client.post("/api/workspaces", json={"name": "Aile"})
    wsid = r.json()["id"]
    u1, u2, _ = users
    r = client.request("DELETE", f"/api/workspaces/{wsid}/members/{u1.id}",
                       headers={"X-Workspace-Id": str(wsid)})
    assert r.status_code == 400  # owner çıkarılamaz


def test_personal_workspace_uye_cikarilamaz(client, db, users):
    u1, u2, ws = users  # ws personal
    r = client.request("DELETE", f"/api/workspaces/{ws.id}/members/{u1.id}",
                       headers={"X-Workspace-Id": str(ws.id)})
    assert r.status_code == 400
