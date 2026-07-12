"""
FEAT-032 — istek listesi / 24-saat impuls bekleme. add/list/resolve + 24h "hazır" işareti.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, WishlistItem


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_add_list_pending(client, db):
    r = client.post("/api/wishlist", json={"item": "Kulaklık", "amount": 3000, "note": "kablosuz"})
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert r.json()["hazir"] is False        # yeni → 24h geçmedi
    body = client.get("/api/wishlist").json()
    assert body["bekleyen_adet"] == 1 and body["review_adet"] == 0


def test_24h_gecince_review_hazir(client, db):
    # 25 saat önce eklenmiş → hazir=True, review_adet=1
    db.add(WishlistItem(user_id=1, item="Telefon", amount=25000, status="pending",
                        created_at=datetime.utcnow() - timedelta(hours=25)))
    db.commit()
    body = client.get("/api/wishlist").json()
    assert body["review_adet"] == 1
    assert body["items"][0]["hazir"] is True


def test_resolve_bought_dismissed(client, db):
    wid = client.post("/api/wishlist", json={"item": "X", "amount": 100}).json()["id"]
    r = client.post(f"/api/wishlist/{wid}/resolve?status=dismissed")
    assert r.status_code == 200 and r.json()["status"] == "dismissed"
    # artık pending değil → listede yok
    assert client.get("/api/wishlist").json()["bekleyen_adet"] == 0
    # tekrar resolve → 409
    assert client.post(f"/api/wishlist/{wid}/resolve?status=bought").status_code == 409


def test_resolve_gecersiz_status_422(client, db):
    wid = client.post("/api/wishlist", json={"item": "X", "amount": 100}).json()["id"]
    assert client.post(f"/api/wishlist/{wid}/resolve?status=xxx").status_code == 422


def test_resolve_yok_404(client, db):
    assert client.post("/api/wishlist/9999/resolve?status=bought").status_code == 404


def test_negatif_tutar_422(client, db):
    assert client.post("/api/wishlist", json={"item": "X", "amount": -5}).status_code == 422
