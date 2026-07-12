"""
GET /api/coach/history — sohbet geçmişi + #092 UTC timestamp serileştirme (uçtan uca).
Backend datetime naive-UTC; UtcDateTime ile +00:00 suffix'li gitmeli (frontend -3h kaymasın).
"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, CoachMemory


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
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


def test_history_bos(client):
    r = client.get("/api/coach/history")
    assert r.status_code == 200
    assert r.json() == []


def test_history_092_utc_suffix(client, db_session):
    db_session.add(CoachMemory(user_id=1, role="assistant", content="Kart borcun 42.100 TL.",
                               timestamp=datetime(2026, 5, 1, 9, 30, 0)))
    db_session.commit()
    body = client.get("/api/coach/history").json()
    assert len(body) == 1
    item = body[0]
    assert item["content"] == "Kart borcun 42.100 TL."
    # #092: naive-UTC → +00:00 suffix (frontend doğru parse etsin)
    assert item["timestamp"].endswith("+00:00"), item["timestamp"]
    assert item["created_at"].endswith("+00:00"), item["created_at"]


def test_history_tool_satiri_gizlenir(client, db_session):
    """BUG #040: role='tool' satırları history'de gösterilmez (kullanıcıya iç kayıt sızmaz)."""
    db_session.add(CoachMemory(user_id=1, role="assistant", content="cevap",
                               timestamp=datetime(2026, 5, 1, 9, 0, 0)))
    db_session.add(CoachMemory(user_id=1, role="tool", content="action_id=5, status=pending",
                               timestamp=datetime(2026, 5, 1, 9, 1, 0)))
    db_session.commit()
    body = client.get("/api/coach/history").json()
    roles = [i["role"] for i in body]
    assert "tool" not in roles
