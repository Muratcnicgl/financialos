"""
goals router — kullanıcı izolasyonu (güvenlik). Her endpoint Goal.user_id == current_user
ile kapsamlı; başka kullanıcının hedefine erişilemez/değiştirilemez/silinemez (404).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add_all([User(id=1, name="murat"), User(id=2, name="baskasi")])
    s.commit()
    yield s
    s.close()


def _client(db_session, uid):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, uid)
    return TestClient(app)


def _create_goal(client):
    r = client.post("/api/goals", json={
        "goal_type": "cash_target", "title": "Tatil", "target_amount": 30000,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_create_goal_user_id_kimlikten_gelir(db_session):
    try:
        c1 = _client(db_session, 1)
        gid = _create_goal(c1)
    finally:
        app.dependency_overrides.clear()
    # user 2 bu hedefi görememeli
    try:
        c2 = _client(db_session, 2)
        assert c2.get(f"/api/goals/{gid}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_baska_kullanici_erisemez_degistiremez_silemez(db_session):
    try:
        c1 = _client(db_session, 1)
        gid = _create_goal(c1)
    finally:
        app.dependency_overrides.clear()

    try:
        c2 = _client(db_session, 2)
        assert c2.get(f"/api/goals/{gid}").status_code == 404
        assert c2.patch(f"/api/goals/{gid}", json={"title": "hack"}).status_code == 404
        assert c2.delete(f"/api/goals/{gid}").status_code == 404
        assert c2.post(f"/api/goals/{gid}/refresh").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_sahip_erisebilir(db_session):
    try:
        c1 = _client(db_session, 1)
        gid = _create_goal(c1)
        assert c1.get(f"/api/goals/{gid}").status_code == 200
        assert c1.patch(f"/api/goals/{gid}", json={"title": "Yaz Tatili"}).status_code == 200
    finally:
        app.dependency_overrides.clear()
