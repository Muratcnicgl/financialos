"""Tests for GET /api/coach/trace/{memory_id}.

Verifies the endpoint implements the resource-hiding security pattern:
- success returns 200 with ordered steps
- unauthorized memory_id (other user's) returns 404 (not 403)
- valid memory_id without a recorded trace returns 404
- nonexistent memory_id returns 404
- multiple steps come back sorted by step_index ASC
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, CoachMemory, OperationName, ReasoningTrace, User


# ----------------------------------------------------------------------
# In-memory engine + session factory (file-scope, mirrors trace integration test)
# ----------------------------------------------------------------------

@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
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
    u = User(name="alice")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def user_bob(db_session: Session) -> User:
    u = User(name="bob")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def client(db_session: Session, user_alice: User):
    """TestClient that injects db_session and authenticates as alice."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user_alice
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _make_memory(db: Session, user: User, content: str = "test reply") -> CoachMemory:
    mem = CoachMemory(user_id=user.id, role="assistant", content=content)
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem


def _make_step(
    db: Session,
    user: User,
    memory: CoachMemory,
    step_index: int,
    operation: OperationName,
    trace_id: str = "trace-uuid-001",
    parent_step_id: int | None = None,
    intent: str | None = None,
) -> ReasoningTrace:
    step = ReasoningTrace(
        user_id=user.id,
        trace_id=trace_id,
        step_index=step_index,
        operation_name=operation,
        coach_memory_id=memory.id,
        parent_step_id=parent_step_id,
        intent=intent,
        created_at=datetime.now(timezone.utc),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def test_get_trace_success(client, db_session, user_alice):
    memory = _make_memory(db_session, user_alice)
    _make_step(db_session, user_alice, memory, 0, OperationName.RULE_CHECK,
               intent="Cockpit kontrolu")
    _make_step(db_session, user_alice, memory, 1, OperationName.LLM_CALL,
               intent="LLM cagrisi")
    _make_step(db_session, user_alice, memory, 2, OperationName.FINAL_ANSWER,
               intent="Nihai cevap")

    resp = client.get(f"/api/coach/trace/{memory.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["coach_memory_id"] == memory.id
    assert body["trace_id"] == "trace-uuid-001"
    assert len(body["steps"]) == 3
    assert [s["step_index"] for s in body["steps"]] == [0, 1, 2]
    assert [s["operation_name"] for s in body["steps"]] == [
        "rule_check", "llm_call", "final_answer",
    ]


def test_get_trace_other_user_returns_404(client, db_session, user_alice, user_bob):
    # Bob has a memory + trace; Alice tries to read it.
    bob_memory = _make_memory(db_session, user_bob, content="bob secret")
    _make_step(db_session, user_bob, bob_memory, 0, OperationName.FINAL_ANSWER)

    resp = client.get(f"/api/coach/trace/{bob_memory.id}")

    # Resource hiding: 404 not 403, no leak about existence.
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Trace bulunamadi"


def test_get_trace_no_trace_returns_404(client, db_session, user_alice):
    # CoachMemory exists for alice but no ReasoningTrace rows.
    memory = _make_memory(db_session, user_alice, content="reply with no trace")

    resp = client.get(f"/api/coach/trace/{memory.id}")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Trace bulunamadi"


def test_get_trace_invalid_memory_id_returns_404(client):
    resp = client.get("/api/coach/trace/999999")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Trace bulunamadi"


def test_get_trace_steps_ordered_by_step_index(client, db_session, user_alice):
    # Insert out of order to verify ORDER BY step_index ASC, not insertion order.
    memory = _make_memory(db_session, user_alice)
    _make_step(db_session, user_alice, memory, 2, OperationName.FINAL_ANSWER)
    _make_step(db_session, user_alice, memory, 0, OperationName.RULE_CHECK)
    _make_step(db_session, user_alice, memory, 1, OperationName.LLM_CALL)

    resp = client.get(f"/api/coach/trace/{memory.id}")

    assert resp.status_code == 200
    steps = resp.json()["steps"]
    assert [s["step_index"] for s in steps] == [0, 1, 2]
