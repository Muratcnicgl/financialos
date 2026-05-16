"""
Tests for POST /api/premortem/{action_id}.

Fixture pattern: in-memory SQLite + dependency_overrides (test_trace_endpoint.py taklit).
generate_premortem LLM cagrisi mock'lanir — network/API key gerekmez.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import ActionStatus, Base, DecisionJournal, PendingAction, User
from app.premortem import PremortemResult, PremortemScenario


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def engine():
    # StaticPool: tum kod ayni SQLite :memory: baglantiyi kullanir.
    # QueuePool'da commit sonrasi baglanti pool'a donuyor ve yeni :memory: DB geliyor.
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
    u = User(name="alice_premortem")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def user_bob(db_session: Session) -> User:
    u = User(name="bob_premortem")
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
# YARDIMCI FACTORY'LER
# ============================================================

def _make_pending_action(
    db: Session,
    user_id: int,
    status: ActionStatus = ActionStatus.pending,
    action_type: str = "add_transaction",
    payload: dict | None = None,
    summary: str = "Market harcamasi",
) -> PendingAction:
    import json
    p = PendingAction(
        user_id=user_id,
        action_type=action_type,
        payload=json.dumps(payload or {"amount": 1500.0, "account_name": "Enpara Nakit"}),
        summary=summary,
        status=status,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_scenarios(n: int = 5) -> list[PremortemScenario]:
    return [
        PremortemScenario(
            id=f"S{i + 1}",
            title=f"Test senaryo {i + 1}",
            probability_label="orta",
            impact_tl=-500.0,
            narrative="Bu aksiyon basarisiz oldu cunku test sebebi yeterli uzunlukta yazildi.",
            mitigation="Test mitigation aksiyonu yazildi.",
        )
        for i in range(n)
    ]


def _make_mock_result(action_id: int, n: int = 5) -> PremortemResult:
    return PremortemResult(
        action_id=action_id,
        scenarios=_make_scenarios(n),
        provider_used="groq",
        model_name="llama-3.3-70b-versatile",
    )


_FAKE_SNAPSHOT = {
    "snapshot_at": "2026-05-16T12:00:00+00:00",
    "net_worth_tl": 50000.0,
    "cash_tl": 15000.0,
    "card_debt_tl": 5000.0,
    "loan_debt_tl": 0.0,
    "investment_tl": 40000.0,
    "cashflow_30d_tl": 7000.0,
    "cashflow_60d_tl": 14000.0,
    "lowest_balance_tl": 12000.0,
    "lowest_balance_date": "2026-06-01",
    "crunch_count": 0,
    "daily_limit_tl": 250.0,
}


@pytest.fixture
def mock_snapshot(monkeypatch):
    """build_cockpit_snapshot + compute_snapshot_hash'i mock'lar."""
    monkeypatch.setattr(
        "app.routers.premortem.build_cockpit_snapshot",
        lambda db, user_id: _FAKE_SNAPSHOT,
    )
    monkeypatch.setattr(
        "app.routers.premortem.compute_snapshot_hash",
        lambda snapshot: "deadbeefcafe1234",
    )


# ============================================================
# TESTLER
# ============================================================

@patch("app.routers.premortem.generate_premortem")
def test_premortem_happy_path(mock_generate, mock_snapshot, client, db_session, user_alice):
    """200: 5 senaryo, DJ kaydedildi, premortem_run_at + snapshot_hash doldu."""
    action = _make_pending_action(db_session, user_alice.id)
    mock_generate.return_value = _make_mock_result(action.id)

    resp = client.post(f"/api/premortem/{action.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["scenarios"]) == 5
    assert body["provider_used"] == "groq"
    assert body["model_name"] == "llama-3.3-70b-versatile"
    assert isinstance(body["persisted_decision_journal_id"], int)
    assert body["cached"] is False

    # DB dogrulama
    import json as _json
    dj = db_session.execute(
        select(DecisionJournal).where(
            DecisionJournal.id == body["persisted_decision_journal_id"]
        )
    ).scalar_one()
    persisted = _json.loads(dj.premortem_scenarios)
    assert len(persisted) == 5
    assert dj.premortem_run_at is not None
    assert dj.cockpit_snapshot_hash == "deadbeefcafe1234"


@patch("app.routers.premortem.generate_premortem")
def test_premortem_404_yanlis_action_id(mock_generate, client):
    """Olmayan action_id icin 404 doner."""
    resp = client.post("/api/premortem/999999")

    assert resp.status_code == 404
    assert "bulunamadi" in resp.json()["detail"].lower()
    mock_generate.assert_not_called()


@patch("app.routers.premortem.generate_premortem")
def test_premortem_404_baska_kullanicinin_actioni(mock_generate, db_session, user_alice, user_bob):
    """Alice'in aksiyonuna Bob erismeye calisiyor — 404 (sahiplik kontrolu)."""
    alice_action = _make_pending_action(db_session, user_alice.id)

    # Bob olarak authenticate et
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user_bob
    bob_client = TestClient(app)
    try:
        resp = bob_client.post(f"/api/premortem/{alice_action.id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
    mock_generate.assert_not_called()


@patch("app.routers.premortem.generate_premortem")
def test_premortem_409_approved_aksiyon(mock_generate, client, db_session, user_alice):
    """Approved status'taki aksiyon icin 409 doner."""
    action = _make_pending_action(db_session, user_alice.id, status=ActionStatus.approved)

    resp = client.post(f"/api/premortem/{action.id}")

    assert resp.status_code == 409
    detail = resp.json()["detail"].lower()
    assert "pending" in detail or "bekleyen" in detail
    mock_generate.assert_not_called()


@patch("app.routers.premortem.generate_premortem")
def test_premortem_503_llm_fail(mock_generate, client, db_session, user_alice):
    """LLM motoru hata verince 503 doner."""
    from app.premortem import PremortemError
    action = _make_pending_action(db_session, user_alice.id)
    mock_generate.side_effect = PremortemError("Tum providerlar quota dolu.")

    resp = client.post(f"/api/premortem/{action.id}")

    assert resp.status_code == 503
    assert "motoru" in resp.json()["detail"].lower()


@patch("app.routers.premortem.generate_premortem")
def test_premortem_idempotent_rerun(mock_generate, mock_snapshot, client, db_session, user_alice):
    """Ayni aksiyon icin iki kez POST — DB'de tek DJ kaydi, ikinci run_at >= birinci."""
    import json
    action = _make_pending_action(db_session, user_alice.id)
    mock_generate.return_value = _make_mock_result(action.id)

    resp1 = client.post(f"/api/premortem/{action.id}")
    assert resp1.status_code == 200
    dj_id_1 = resp1.json()["persisted_decision_journal_id"]

    # Ikinci cagri
    mock_generate.return_value = _make_mock_result(action.id)
    resp2 = client.post(f"/api/premortem/{action.id}")
    assert resp2.status_code == 200
    dj_id_2 = resp2.json()["persisted_decision_journal_id"]

    # Ayni DJ guncellendiginden ID ayni olmali
    assert dj_id_1 == dj_id_2

    # DB'de sadece 1 kayit
    rows = db_session.execute(
        select(DecisionJournal).where(
            DecisionJournal.decision_text == f"PendingAction#{action.id}"
        )
    ).scalars().all()
    assert len(rows) == 1

    # Senaryolar son yazilanlar
    persisted = json.loads(rows[0].premortem_scenarios)
    assert len(persisted) == 5
    assert rows[0].premortem_run_at is not None
