"""
TraceRecorder birim testleri (Wave-2 H1G3 Asama 2.1).
"""

from __future__ import annotations

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    CoachMemory,
    OperationName,
    ReasoningTrace,
    User,
)
from app.reasoning_trace import TraceRecorder


@pytest.fixture
def db_session():
    """In-memory SQLite session, her test fresh DB."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, name="test")
    session.add(user)
    session.commit()
    yield session
    session.close()


def test_basic_step_recording(db_session):
    """Tek step yazilir, alanlar dogru kaydedilir."""
    recorder = TraceRecorder(db_session, user_id=1)

    with recorder.step(OperationName.RULE_CHECK, intent="MC4 kontrolu") as s:
        s.observation = "MC4 tetiklendi"
        s.inference = "LLM'e baglam ver"

    rows = db_session.query(ReasoningTrace).all()
    assert len(rows) == 1
    r = rows[0]
    assert r.user_id == 1
    assert r.trace_id == recorder.trace_id
    assert r.step_index == 0
    assert r.operation_name == OperationName.RULE_CHECK
    assert r.intent == "MC4 kontrolu"
    assert r.observation == "MC4 tetiklendi"
    assert r.inference == "LLM'e baglam ver"
    assert r.coach_memory_id is None
    assert r.latency_ms is not None and r.latency_ms >= 0


def test_multiple_steps_increment_index(db_session):
    """Step index her cagrida artar."""
    recorder = TraceRecorder(db_session, user_id=1)

    with recorder.step(OperationName.RULE_CHECK, intent="step 0"):
        pass
    with recorder.step(OperationName.LLM_CALL, intent="step 1"):
        pass
    with recorder.step(OperationName.FINAL_ANSWER, intent="step 2"):
        pass

    rows = db_session.query(ReasoningTrace).order_by(ReasoningTrace.step_index).all()
    assert len(rows) == 3
    assert [r.step_index for r in rows] == [0, 1, 2]
    assert [r.operation_name for r in rows] == [
        OperationName.RULE_CHECK,
        OperationName.LLM_CALL,
        OperationName.FINAL_ANSWER,
    ]


def test_explicit_parent_step_id(db_session):
    """Retry icin parent_step_id explicit gecilebilir."""
    recorder = TraceRecorder(db_session, user_id=1)

    with recorder.step(OperationName.LLM_CALL, intent="ilk LLM call") as s:
        pass  # block exit'te step_db_id set edilir

    # Block disinda step_db_id artik dolu
    first_row = db_session.query(ReasoningTrace).filter_by(step_index=0).first()
    real_parent_id = first_row.id

    with recorder.step(OperationName.LLM_CALL, intent="retry", parent_step_id=real_parent_id):
        pass

    second = db_session.query(ReasoningTrace).filter_by(step_index=1).first()
    assert second.parent_step_id == real_parent_id


def test_step_db_id_set_after_block(db_session):
    """Block sonrasi proxy.step_db_id dolar (parent referansi icin kritik)."""
    recorder = TraceRecorder(db_session, user_id=1)

    proxy_ref = None
    with recorder.step(OperationName.LLM_CALL) as s:
        proxy_ref = s

    # Block exit sonrasi step_db_id dolu
    assert proxy_ref.step_db_id is not None

    row = db_session.query(ReasoningTrace).first()
    assert proxy_ref.step_db_id == row.id


def test_action_input_json_helper(db_session):
    """set_action_input() dict'i JSON string'e cevirir."""
    recorder = TraceRecorder(db_session, user_id=1)

    with recorder.step(OperationName.RULE_CHECK) as s:
        s.set_action_input({"rule": "MC4", "params": {"account_id": 42}})

    row = db_session.query(ReasoningTrace).first()
    parsed = json.loads(row.action_input_json)
    assert parsed["rule"] == "MC4"
    assert parsed["params"]["account_id"] == 42


def test_exception_records_error(db_session):
    """Step icinde exception olursa error kolonu dolar, sonra raise."""
    recorder = TraceRecorder(db_session, user_id=1)

    with pytest.raises(ValueError):
        with recorder.step(OperationName.LLM_CALL):
            raise ValueError("test hatasi")

    row = db_session.query(ReasoningTrace).first()
    assert row.error is not None
    assert "ValueError" in row.error
    assert "test hatasi" in row.error
    assert row.latency_ms is not None  # latency yine olculmus olmali


def test_set_coach_memory_id_backfill(db_session):
    """STEP 6 sonrasi tum trace satirlari coach_memory_id ile guncellenir."""
    cm = CoachMemory(user_id=1, role="user", content="merhaba")
    db_session.add(cm)
    db_session.commit()

    recorder = TraceRecorder(db_session, user_id=1)

    with recorder.step(OperationName.RULE_CHECK):
        pass
    with recorder.step(OperationName.LLM_CALL):
        pass
    with recorder.step(OperationName.FINAL_ANSWER):
        pass

    rows_before = db_session.query(ReasoningTrace).all()
    assert all(r.coach_memory_id is None for r in rows_before)

    recorder.set_coach_memory_id(cm.id)

    db_session.expire_all()
    rows_after = db_session.query(ReasoningTrace).all()
    assert all(r.coach_memory_id == cm.id for r in rows_after)


def test_metadata_fields_recorded(db_session):
    """provider_system, model_name, usage_*, latency dogru kaydedilir."""
    recorder = TraceRecorder(db_session, user_id=1)

    with recorder.step(OperationName.LLM_CALL, intent="test") as s:
        s.provider_system = "groq"
        s.model_name = "llama-3.3-70b-versatile"
        s.usage_input_tokens = 1500
        s.usage_output_tokens = 320
        s.confidence_score = 0.85

    row = db_session.query(ReasoningTrace).first()
    assert row.provider_system == "groq"
    assert row.model_name == "llama-3.3-70b-versatile"
    assert row.usage_input_tokens == 1500
    assert row.usage_output_tokens == 320
    assert row.confidence_score == 0.85
