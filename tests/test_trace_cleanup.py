"""
Tests for nightly_trace_cleanup_job — deletes ReasoningTrace
rows older than 90 days.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.models import Base, ReasoningTrace, User, CoachMemory


# ---------- in-memory engine fixture (matches test_trace_endpoint.py) ----------

@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocalTest = sessionmaker(bind=engine)
    db = SessionLocalTest()
    yield db
    db.close()


@pytest.fixture
def user(session):
    u = User(name="cleanup_user")
    session.add(u)
    session.commit()
    return u


@pytest.fixture
def memory(session, user):
    m = CoachMemory(user_id=user.id, role="assistant", content="test")
    session.add(m)
    session.commit()
    return m


def _make_trace(session, memory, user, age_days, trace_uuid):
    """Insert a ReasoningTrace with created_at backdated by age_days."""
    backdate = datetime.now(timezone.utc) - timedelta(days=age_days)
    tr = ReasoningTrace(
        coach_memory_id=memory.id,
        user_id=user.id,
        trace_id=trace_uuid,
        step_index=0,
        operation_name="final_answer",
        created_at=backdate,
    )
    session.add(tr)
    session.commit()
    return tr


# ---------- tests ----------

def test_cleanup_removes_old_traces(session, memory, user, monkeypatch):
    """Traces older than 90 days are deleted; younger ones survive."""
    _make_trace(session, memory, user, age_days=120, trace_uuid="old-1")
    _make_trace(session, memory, user, age_days=91,  trace_uuid="old-2")
    _make_trace(session, memory, user, age_days=89,  trace_uuid="young-1")
    _make_trace(session, memory, user, age_days=1,   trace_uuid="young-2")

    import app.scheduler as scheduler_mod
    monkeypatch.setattr(scheduler_mod, "SessionLocal", lambda: session)
    original_close = session.close
    session.close = lambda: None
    try:
        asyncio.run(scheduler_mod.nightly_trace_cleanup_job())
    finally:
        session.close = original_close

    remaining = session.execute(select(ReasoningTrace)).scalars().all()
    remaining_ids = sorted(t.trace_id for t in remaining)
    assert remaining_ids == ["young-1", "young-2"]


def test_cleanup_is_idempotent(session, memory, user, monkeypatch):
    """Running cleanup twice produces same result as once."""
    _make_trace(session, memory, user, age_days=89, trace_uuid="young")

    import app.scheduler as scheduler_mod
    monkeypatch.setattr(scheduler_mod, "SessionLocal", lambda: session)
    original_close = session.close
    session.close = lambda: None
    try:
        asyncio.run(scheduler_mod.nightly_trace_cleanup_job())
        asyncio.run(scheduler_mod.nightly_trace_cleanup_job())
    finally:
        session.close = original_close

    total = session.execute(
        select(func.count()).select_from(ReasoningTrace)
    ).scalar()
    assert total == 1


def test_cleanup_empty_table_safe(session, monkeypatch):
    """Cleanup on empty table succeeds without errors."""
    import app.scheduler as scheduler_mod
    monkeypatch.setattr(scheduler_mod, "SessionLocal", lambda: session)
    original_close = session.close
    session.close = lambda: None
    try:
        asyncio.run(scheduler_mod.nightly_trace_cleanup_job())
    finally:
        session.close = original_close

    total = session.execute(
        select(func.count()).select_from(ReasoningTrace)
    ).scalar()
    assert total == 0


def test_cleanup_boundary_exactly_90_days(session, memory, user, monkeypatch):
    """
    Traces created exactly 90 days ago are NOT deleted (strict less-than
    semantics). Important: boundary precision avoids accidentally
    deleting same-day traces.
    """
    # Just under 90 days (89 days): survives.
    _make_trace(session, memory, user, age_days=89, trace_uuid="boundary-survivor")
    # Just over 90 days (91 days): deleted.
    _make_trace(session, memory, user, age_days=91, trace_uuid="boundary-victim")

    import app.scheduler as scheduler_mod
    monkeypatch.setattr(scheduler_mod, "SessionLocal", lambda: session)
    original_close = session.close
    session.close = lambda: None
    try:
        asyncio.run(scheduler_mod.nightly_trace_cleanup_job())
    finally:
        session.close = original_close

    remaining = session.execute(select(ReasoningTrace)).scalars().all()
    remaining_ids = sorted(t.trace_id for t in remaining)
    assert remaining_ids == ["boundary-survivor"]
