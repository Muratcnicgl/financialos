"""
FEAT-033 — Uygulama-içi geri bildirim (Şikayet/İstek/Öneri) endpoint testleri.
POST doğrulama + GET newest-first + KULLANICI İZOLASYONU (kendi kayıtları).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Feedback


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(User(id=2, name="baskasi"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_post_gecerli_201(client):
    r = client.post("/api/feedback", json={"kind": "oneri", "message": "Karanlık tema harika olur"})
    assert r.status_code == 201
    d = r.json()
    assert d["kind"] == "oneri"
    assert d["message"] == "Karanlık tema harika olur"
    assert d["status"] == "new"
    assert d["created_at"].endswith(("Z", "+00:00"))  # UTC suffix (BUG #092)


def test_post_gecersiz_kind_422(client):
    r = client.post("/api/feedback", json={"kind": "spam", "message": "x"})
    assert r.status_code == 422


def test_post_bos_mesaj_422(client):
    r = client.post("/api/feedback", json={"kind": "sikayet", "message": ""})
    assert r.status_code == 422


def test_post_page_baglami_kaydedilir(client):
    r = client.post("/api/feedback", json={
        "kind": "sikayet", "message": "Kokpit yavaş", "page": "Cockpit"})
    assert r.status_code == 201
    assert r.json()["page"] == "Cockpit"


def test_get_newest_first(client):
    client.post("/api/feedback", json={"kind": "oneri", "message": "birinci"})
    client.post("/api/feedback", json={"kind": "istek", "message": "ikinci"})
    r = client.get("/api/feedback")
    assert r.status_code == 200
    msgs = [f["message"] for f in r.json()]
    assert msgs[0] == "ikinci" and msgs[1] == "birinci"  # newest-first


def test_kullanici_izolasyonu(client, db_session):
    """Kullanıcı başkasının geri bildirimini GÖRMEZ (kendi kayıtları)."""
    # user 2 doğrudan DB'ye bir feedback yazar
    from datetime import datetime
    db_session.add(Feedback(user_id=2, kind="sikayet", message="user2 gizli",
                            status="new", created_at=datetime.utcnow()))
    db_session.commit()
    # user 1 kendi bir tane yollar
    client.post("/api/feedback", json={"kind": "oneri", "message": "user1 acik"})
    r = client.get("/api/feedback")
    msgs = [f["message"] for f in r.json()]
    assert "user1 acik" in msgs
    assert "user2 gizli" not in msgs  # izolasyon: başkasının kaydı sızmaz
