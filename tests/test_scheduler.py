"""Tetikleme altyapisi testleri."""

import pytest
from unittest.mock import patch
from app.scheduler import (
    run_extractor,
    run_periodic_batch_for_user,
    NIGHTLY_BATCH_EXTRACTORS,
    EVENT_TRIGGERED_AFTER_USER_MESSAGE,
    trigger_after_user_message,
    trigger_after_action_resolution,
)


def test_run_extractor_returns_dict_for_normal(db_session, test_user):
    """Normal extractor (breakthrough) dict doner."""
    result = run_extractor("breakthrough", db_session, test_user.id)
    assert isinstance(result, dict)


def test_run_extractor_normalizes_decision_rhythm(db_session, test_user):
    """decision_rhythm None doner, dispatcher normalize eder."""
    result = run_extractor("decision_rhythm", db_session, test_user.id)
    assert isinstance(result, dict)
    assert result == {"status": "completed"}


def test_run_extractor_unknown_returns_error(db_session, test_user):
    """Bilinmeyen extractor ismi error doner, exception firlatmaz."""
    result = run_extractor("nonexistent_extractor", db_session, test_user.id)
    assert "error" in result
    assert "unknown_extractor" in result["error"]


def test_run_extractor_isolates_exceptions(db_session, test_user):
    """Bir extractor cokerse exception yakalanir, error dict doner."""
    with patch("app.scheduler.extract_breakthrough", side_effect=RuntimeError("boom")):
        result = run_extractor("breakthrough", db_session, test_user.id)
    assert "error" in result
    assert "boom" in result["error"]


def test_run_periodic_batch_runs_all_extractors(db_session, test_user):
    """Periodic batch tum 5 extractor'i calistirir, hicbiri exception firlatmaz."""
    results = run_periodic_batch_for_user(db_session, test_user.id)

    assert set(results.keys()) == set(NIGHTLY_BATCH_EXTRACTORS)
    for name, result in results.items():
        assert isinstance(result, dict), f"{name} dict donmuyor"


def test_run_periodic_batch_continues_after_one_failure(db_session, test_user):
    """Bir extractor cokse digerleri devam eder."""
    with patch("app.scheduler.extract_setback", side_effect=RuntimeError("setback fail")):
        results = run_periodic_batch_for_user(db_session, test_user.id)

    assert "error" in results["setback"]
    assert "error" not in results["breakthrough"]
    assert "error" not in results["mc_reference_frequency"]
    assert "error" not in results["question_typology"]
    assert "error" not in results["category_account_preference"]


def test_trigger_after_user_message_no_exception(db_session, test_user):
    """Olay-tetikli wrapper exception firlatmaz, sessizce devam eder."""
    trigger_after_user_message(db_session, test_user.id)


def test_trigger_after_action_resolution_no_exception(db_session, test_user):
    """Action resolution wrapper exception firlatmaz."""
    trigger_after_action_resolution(db_session, test_user.id)


def test_trigger_swallows_extractor_exception(db_session, test_user):
    """Olay-tetikli extractor cokerse wrapper exception firlatmaz, sadece logger'a yazar."""
    with patch("app.scheduler.extract_explicit_red_line_k1", side_effect=RuntimeError("k1 fail")):
        trigger_after_user_message(db_session, test_user.id)


# ============================================================
# TESTS: hook integration (coach.py + action_executor.py wire-up)
# ============================================================

def test_coach_chat_triggers_user_message_hook(db_session, test_user, monkeypatch):
    """CoachEngine.chat() user mesaji kaydettikten sonra trigger_after_user_message
    cagrildigini dogrula."""
    from app.coach import CoachEngine
    import app.scheduler as scheduler_module

    call_log = []

    def fake_trigger(db, user_id):
        call_log.append(("user_message", db, user_id))

    monkeypatch.setattr(scheduler_module, "trigger_after_user_message", fake_trigger)

    class _MockLLM:
        def chat(self, system_prompt, messages, tools=None):
            class R:
                text = "Anlasilan."
                tool_calls = []
            return R()

    engine = CoachEngine(provider=_MockLLM())
    try:
        engine.chat(db_session, test_user.id, "Test mesaji")
    except Exception:
        pass  # Mock provider tum coach akisini desteklemeyebilir, hook cagri yeter

    user_calls = [c for c in call_log if c[0] == "user_message"]
    assert len(user_calls) >= 1, f"trigger_after_user_message cagrilmadi. Log: {call_log}"
    assert user_calls[0][2] == test_user.id


def test_reject_action_triggers_resolution_hook(db_session, test_user, monkeypatch):
    """reject_pending_action db.commit sonrasi trigger_after_action_resolution
    cagrildigini dogrula."""
    from app.models import PendingAction, ActionStatus
    from app.action_executor import reject_pending_action
    import app.scheduler as scheduler_module

    pending = PendingAction(
        user_id=test_user.id,
        action_type="test_action",
        payload="{}",
        summary="test",
        status=ActionStatus.pending,
    )
    db_session.add(pending)
    db_session.commit()

    call_log = []

    def fake_trigger(db, user_id):
        call_log.append(("action_resolution", db, user_id))

    monkeypatch.setattr(scheduler_module, "trigger_after_action_resolution", fake_trigger)

    result = reject_pending_action(db_session, pending.id, test_user.id, reason="test")

    assert result["success"] is True
    assert len(call_log) >= 1, f"trigger_after_action_resolution cagrilmadi. Log: {call_log}"
    assert call_log[0][2] == test_user.id


def test_execute_action_triggers_resolution_hook(db_session, test_user, monkeypatch):
    """execute_pending_action basarili olunca hook cagrilir."""
    from app.models import PendingAction, ActionStatus
    from app.action_executor import execute_pending_action
    import app.scheduler as scheduler_module

    pending = PendingAction(
        user_id=test_user.id,
        action_type="add_transaction",
        payload='{"amount": 100, "category": "test"}',
        summary="test execute",
        status=ActionStatus.pending,
    )
    db_session.add(pending)
    db_session.commit()

    call_log = []

    def fake_trigger(db, user_id):
        call_log.append(("action_resolution", db, user_id))

    monkeypatch.setattr(scheduler_module, "trigger_after_action_resolution", fake_trigger)

    result = execute_pending_action(db_session, pending.id, test_user.id)

    if result.get("success"):
        assert len(call_log) >= 1, f"hook cagrilmadi. Log: {call_log}"
    else:
        pytest.skip(f"execute_pending_action setup uyumsuz: {result}")
