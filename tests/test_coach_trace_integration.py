"""
CoachEngine.chat() trace entegrasyon testleri (Wave-2 H1G3 Asama 2.3).
FakeProvider ile gercek LLM cagrisi yapilmaz.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, CoachMemory, OperationName, ReasoningTrace, User
from app.coach import CoachEngine, LLMResponse


class FakeProvider:
    NAME = "Fake"
    model = "fake-model-1"
    last_used_provider = "fake"

    def chat(self, system_prompt, messages, tools=None):
        return LLMResponse(
            text="Test cevap.",
            tool_calls=[],
            usage={"input_tokens": 100, "output_tokens": 50},
            provider_used="fake",
            model_name="fake-model-1",
        )


@pytest.fixture
def mem_db():
    """In-memory SQLite, her test fresh DB - conftest db_session'dan bagımsız."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, name="trace_test_user")
    session.add(user)
    session.commit()
    yield session, user
    session.close()


def test_chat_creates_traces_for_simple_question(mem_db):
    """chat() cagrisinin en az 4 trace satiri birakmasi gerekiyor:
    RULE_CHECK + OBSERVATION + LLM_CALL + FINAL_ANSWER."""
    db, user = mem_db
    engine = CoachEngine(provider=FakeProvider())

    engine.chat(db, user.id, "Bu ay butcem nasil?", include_cockpit=False)

    db.expire_all()
    traces = db.query(ReasoningTrace).order_by(ReasoningTrace.step_index).all()

    assert len(traces) >= 4, f"Beklenen >= 4 trace, gelen: {len(traces)}"

    # Hepsi ayni trace_id
    trace_ids = {t.trace_id for t in traces}
    assert len(trace_ids) == 1, "Tum satirlar ayni trace_id'de olmali"

    # Step index siralanmis, 0'dan baslayan
    indices = [t.step_index for t in traces]
    assert indices == list(range(len(traces))), f"step_index siralamasi bozuk: {indices}"

    # Beklenen operation tipler (sirayla)
    ops = [t.operation_name for t in traces]
    assert ops[0] == OperationName.RULE_CHECK
    assert ops[1] == OperationName.OBSERVATION
    assert ops[2] == OperationName.LLM_CALL
    assert ops[-1] == OperationName.FINAL_ANSWER


def test_chat_records_provider_metadata(mem_db):
    """LLM_CALL step'inde provider/model/usage alanlari dogru kaydedilmis olmali."""
    db, user = mem_db
    engine = CoachEngine(provider=FakeProvider())

    engine.chat(db, user.id, "Test mesaji.", include_cockpit=False)

    db.expire_all()
    llm_step = (
        db.query(ReasoningTrace)
        .filter_by(operation_name=OperationName.LLM_CALL)
        .order_by(ReasoningTrace.step_index)
        .first()
    )
    assert llm_step is not None
    assert llm_step.provider_system == "fake"
    assert llm_step.model_name == "fake-model-1"
    assert llm_step.usage_input_tokens == 100
    assert llm_step.usage_output_tokens == 50
    assert llm_step.latency_ms is not None and llm_step.latency_ms >= 0


def test_chat_backfills_coach_memory_id(mem_db):
    """chat() sonrasi tum trace satirlarinda coach_memory_id dolu olmali
    ve assistant CoachMemory.id ile eslesmeli."""
    db, user = mem_db
    engine = CoachEngine(provider=FakeProvider())

    engine.chat(db, user.id, "Backfill testi.", include_cockpit=False)

    db.expire_all()
    traces = db.query(ReasoningTrace).filter_by(user_id=user.id).all()
    assert len(traces) >= 1

    # Hepsinde coach_memory_id dolu
    null_traces = [t for t in traces if t.coach_memory_id is None]
    assert len(null_traces) == 0, f"{len(null_traces)} trace'de coach_memory_id hala NULL"

    # Assistant CoachMemory satiriyla eslesiyor
    assistant_mem = (
        db.query(CoachMemory)
        .filter_by(user_id=user.id, role="assistant")
        .order_by(CoachMemory.timestamp.desc())
        .first()
    )
    assert assistant_mem is not None
    assert all(t.coach_memory_id == assistant_mem.id for t in traces), (
        f"Trace'ler farkli coach_memory_id'e isaret ediyor: "
        f"{set(t.coach_memory_id for t in traces)} != {assistant_mem.id}"
    )
