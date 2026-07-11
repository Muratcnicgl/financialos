"""
BE-009: /api/coach/chat hata yönetimi — ham hata (str(e)) kullanıcıya SIZDIRILMAZ.
Graceful degradation (chat UX için 200) ama gerçek hata loglanır, kullanıcıya genel mesaj.
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


class _FailEngine:
    provider_name = "ScriptedProvider"
    model = "scripted-1"

    def chat(self, **kw):
        raise RuntimeError("SECRET-INTERNAL-DETAIL stack xyz")


def test_chat_hata_ham_detay_sizdirmaz(client, monkeypatch):
    monkeypatch.setattr("app.routers.coach._get_engine", lambda: _FailEngine())
    r = client.post("/api/coach/chat", json={"message": "selam", "include_cockpit": False})
    assert r.status_code == 200                      # graceful (chat UX)
    body = r.json()
    assert "SECRET-INTERNAL-DETAIL" not in body["reply"]   # ham hata sızmıyor
    assert "cevap veremedi" in body["reply"].lower()
    assert body["proposed_actions"] == []
