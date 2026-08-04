"""
Tests for POST /api/simulate/{action_id}.
StaticPool :memory: SQLite + dependency_overrides pattern (test_premortem_endpoint.py taklit).
simulate_action LLM/DB agir hesabi monkeypatch ile mock'lanir.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import ActionStatus, Base, PendingAction, User


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user_alice(db_session: Session) -> User:
    u = User(name="alice_sim")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def user_bob(db_session: Session) -> User:
    u = User(name="bob_sim")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def client(db_session: Session, user_alice: User):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user_alice
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ============================================================
# FACTORY
# ============================================================

def _make_action(
    db: Session,
    user_id: int,
    status: ActionStatus = ActionStatus.pending,
    action_type: str = "add_transaction",
    payload: dict | None = None,
    summary: str = "Test harcamasi",
) -> PendingAction:
    p = PendingAction(
        user_id=user_id,
        action_type=action_type,
        payload=json.dumps(payload or {
            "amount": 1000.0,
            "account_id": 1,
            "transaction_type": "expense",
            "category": "yemek",
        }),
        summary=summary,
        status=status,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


_MOCK_RESULT = {
    "ok": True,
    "message": "Simulasyon basarili",
    "baseline": {"nakit_kasa": 5000.0, "net_deger": -50000.0},
    "snapshots": [
        {
            "label": "T+0",
            "nakit_kasa": 4000.0, "kart_borcu": 5000.0, "kredi_borcu": 60000.0,
            "yatirim_deger": 30000.0, "net_deger": -31000.0,
            "delta_vs_baseline": {"net_deger": -1000.0},
        },
        {
            "label": "T+30",
            "nakit_kasa": 11000.0, "kart_borcu": 5500.0, "kredi_borcu": 57000.0,
            "yatirim_deger": 30000.0, "net_deger": -21500.0,
            "delta_vs_baseline": {"net_deger": -1000.0},
        },
        {
            "label": "T+90",
            "nakit_kasa": 25000.0, "kart_borcu": 6500.0, "kredi_borcu": 51000.0,
            "yatirim_deger": 30000.0, "net_deger": -2500.0,
            "delta_vs_baseline": {"net_deger": -1000.0},
        },
    ],
    "event_log": ["1000 TL yemek gideri"],
    "comparison": {"net_worth_change_30d": -1000.0, "cash_change_30d": -1000.0},
}


# ============================================================
# TESTLER
# ============================================================

@patch("app.routers.simulation.simulate_action")
def test_simulate_happy_path(mock_sim, client, db_session, user_alice):
    """200: 3 ufuk, summary, event_log doğru gelir."""
    action = _make_action(db_session, user_alice.id)
    mock_sim.return_value = _MOCK_RESULT

    resp = client.post(f"/api/simulate/{action.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(body["horizons"]) == 3

    h0, h30, h90 = body["horizons"]
    assert h0["label"] == "T+0"  and h0["days"] == 0
    assert h30["label"] == "T+30" and h30["days"] == 30
    assert h90["label"] == "T+90" and h90["days"] == 90

    assert body["summary"]["net_worth_change_30d"] == -1000.0
    assert "event_log" in body
    assert len(body["event_log"]) >= 1


@patch("app.routers.simulation.simulate_action")
def test_simulate_404_yanlis_action_id(mock_sim, client):
    """Olmayan action_id icin 404 doner."""
    resp = client.post("/api/simulate/999999")

    assert resp.status_code == 404
    assert "bulunamadi" in resp.json()["detail"].lower()
    mock_sim.assert_not_called()


@patch("app.routers.simulation.simulate_action")
def test_simulate_404_baska_kullanicinin_actioni(mock_sim, db_session, user_alice, user_bob):
    """Alice'in aksiyonuna Bob erismeye calisiyor — 404."""
    alice_action = _make_action(db_session, user_alice.id)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user_bob
    bob_client = TestClient(app)
    try:
        resp = bob_client.post(f"/api/simulate/{alice_action.id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
    mock_sim.assert_not_called()


@patch("app.routers.simulation.simulate_action")
def test_simulate_409_approved_aksiyon(mock_sim, client, db_session, user_alice):
    """Approved aksiyon icin 409 doner."""
    action = _make_action(db_session, user_alice.id, status=ActionStatus.approved)

    resp = client.post(f"/api/simulate/{action.id}")

    assert resp.status_code == 409
    detail = resp.json()["detail"].lower()
    assert "bekleyen" in detail or "pending" in detail
    mock_sim.assert_not_called()


@patch("app.routers.simulation.simulate_action")
def test_simulate_500_engine_exception(mock_sim, client, db_session, user_alice):
    """Engine exception firlatinca 500 doner."""
    action = _make_action(db_session, user_alice.id)
    mock_sim.side_effect = Exception("engine cokmesi")

    resp = client.post(f"/api/simulate/{action.id}")

    assert resp.status_code == 500
    # BUG #175 (P2): ham exception metni ("engine cokmesi") kullanıcıya DÖNMEZ.
    detay = resp.json()["detail"]
    assert "simulasyon" in detay.lower()
    assert "cokmesi" not in detay.lower(), f"İç hata metni sızdı: {detay}"
