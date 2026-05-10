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
