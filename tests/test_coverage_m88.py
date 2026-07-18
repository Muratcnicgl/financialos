"""
M88 — Kapsam artırıcı testler (%90 → %92 hedefi).

Dış API çağrısı YOK: LLM FakeProvider/monkeypatch, TEFAS/pytefas sahte modül,
OAuth2Session mock, SMTP send_email stub. In-memory SQLite (StaticPool) izole DB.

Hedef modüller: scheduler (job gövdeleri + lifecycle), coach pure helper'lar,
fund_tracker (freshness + try_auto_fetch), oauth (exchange_code dalları),
workspace_invite (send_email + type guard), workspace_deps (fail-fast + require_write).
"""
from __future__ import annotations

import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Account, AccountType, ReasoningTrace, OperationName,
    Workspace, WorkspaceMembership, WorkspaceRole,
)


def _session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), engine


# ============================================================
# SCHEDULER — job gövdeleri + lifecycle
# ============================================================

def test_db_session_contextmanager_yields_and_closes(monkeypatch):
    from app import scheduler
    Session, _ = _session_factory()
    monkeypatch.setattr(scheduler, "SessionLocal", Session)
    with scheduler._db_session() as db:
        assert db.query(User).all() == []
    # kapandıktan sonra tekrar sorgu bind kaybetmez (StaticPool) ama context çıktı


def test_get_active_user_ids_returns_all(monkeypatch):
    from app import scheduler
    Session, _ = _session_factory()
    db = Session()
    db.add_all([User(name="a"), User(name="b")])
    db.commit()
    ids = scheduler._get_active_user_ids(db)
    assert len(ids) == 2
    db.close()


def test_run_k2_batch_for_user_returns_k2_key(db_session, test_user):
    from app import scheduler
    result = scheduler.run_k2_batch_for_user(db_session, test_user.id)
    assert scheduler.K2_BATCH_EXTRACTOR in result
    assert isinstance(result[scheduler.K2_BATCH_EXTRACTOR], dict)


def test_run_extractor_k2_branch(db_session, test_user):
    from app import scheduler
    result = scheduler.run_extractor("explicit_red_line_k2", db_session, test_user.id)
    assert isinstance(result, dict)


def test_nightly_batch_job_runs_for_all_users(monkeypatch):
    from app import scheduler
    Session, _ = _session_factory()
    seed = Session()
    seed.add_all([User(name="u1"), User(name="u2")])
    seed.commit()
    seed.close()
    monkeypatch.setattr(scheduler, "SessionLocal", Session)
    # exception fırlatmamalı
    asyncio.run(scheduler.nightly_batch_job())


def test_nightly_batch_job_survives_global_failure(monkeypatch):
    from app import scheduler

    class _BoomSession:
        def __call__(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(scheduler, "SessionLocal", _BoomSession())
    # global try/except yakalar, exception dışarı sızmaz
    asyncio.run(scheduler.nightly_batch_job())


def test_k2_batch_job_runs(monkeypatch):
    from app import scheduler
    Session, _ = _session_factory()
    seed = Session()
    seed.add(User(name="u1"))
    seed.commit()
    seed.close()
    monkeypatch.setattr(scheduler, "SessionLocal", Session)
    asyncio.run(scheduler.k2_batch_job())


def test_k2_batch_job_survives_global_failure(monkeypatch):
    from app import scheduler

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(scheduler, "SessionLocal", _boom)
    asyncio.run(scheduler.k2_batch_job())


def test_trace_cleanup_deletes_old_rows(monkeypatch):
    from app import scheduler
    Session, _ = _session_factory()
    seed = Session()
    u = User(name="u1")
    seed.add(u)
    seed.commit()
    old = ReasoningTrace(
        user_id=u.id, trace_id="t-old", step_index=0,
        operation_name=OperationName.LLM_CALL,
        created_at=datetime.utcnow() - timedelta(days=120),
    )
    fresh = ReasoningTrace(
        user_id=u.id, trace_id="t-new", step_index=0,
        operation_name=OperationName.LLM_CALL,
        created_at=datetime.utcnow(),
    )
    seed.add_all([old, fresh])
    seed.commit()
    seed.close()
    monkeypatch.setattr(scheduler, "SessionLocal", Session)
    asyncio.run(scheduler.nightly_trace_cleanup_job())
    check = Session()
    remaining = check.query(ReasoningTrace).all()
    assert len(remaining) == 1
    assert remaining[0].trace_id == "t-new"
    check.close()


def test_trace_cleanup_reraises_on_failure(monkeypatch):
    from app import scheduler

    class _BadSession:
        def execute(self, *a, **k):
            raise RuntimeError("execute fail")

        def rollback(self):
            self.rolled_back = True

        def commit(self):
            pass

        def close(self):
            pass

    bad = _BadSession()
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: bad)
    with pytest.raises(RuntimeError, match="execute fail"):
        asyncio.run(scheduler.nightly_trace_cleanup_job())
    assert getattr(bad, "rolled_back", False) is True


def test_price_job_survives_fetch_exception(monkeypatch):
    """fetch_for_account exception fırlatırsa job içindeki iç try onu yakalar (245-247)."""
    from app import scheduler, price_providers
    Session, _ = _session_factory()
    seed = Session()
    u = User(name="u1")
    seed.add(u)
    seed.commit()
    seed.add(Account(user_id=u.id, name="Fon", account_type=AccountType.investment,
                     balance=100.0, fund_code="ABC"))
    seed.commit()
    seed.close()
    monkeypatch.setattr(scheduler, "SessionLocal", Session)

    def _boom(acc):
        raise RuntimeError("network fail")

    monkeypatch.setattr(price_providers, "fetch_for_account", _boom)
    asyncio.run(scheduler.fetch_investment_prices_job())  # exception yok
    check = Session()
    acc = check.query(Account).filter(Account.fund_code == "ABC").first()
    assert acc.current_price is None  # çekilemedi
    check.close()


def test_price_job_survives_outer_exception(monkeypatch):
    """DB query patlarsa dış try/except yakalar (257-259)."""
    from app import scheduler

    class _BadSession:
        def query(self, *a, **k):
            raise RuntimeError("query fail")

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    bad = _BadSession()
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: bad)
    asyncio.run(scheduler.fetch_investment_prices_job())  # exception dışarı sızmaz
    assert getattr(bad, "rolled_back", False) is True


def test_weekly_smoke_test_job_survives_failure(monkeypatch):
    """run_all_smoke_tests patlarsa job yutar (283-284)."""
    from app import scheduler
    import app.services.smoke_tests as smoke_mod

    def _boom():
        raise RuntimeError("smoke boom")

    monkeypatch.setattr(smoke_mod, "run_all_smoke_tests", _boom)
    asyncio.run(scheduler.weekly_smoke_test_job())  # exception yok


def test_weekly_smoke_test_job_happy_path(monkeypatch):
    from app import scheduler
    import app.services.smoke_tests as smoke_mod

    monkeypatch.setattr(smoke_mod, "run_all_smoke_tests",
                        lambda: [{"api": "evds", "ok": True, "detail": "200"},
                                 {"api": "smtp", "ok": False, "detail": "timeout"}])
    monkeypatch.setattr(smoke_mod, "capture_smoke_failures", lambda results: 1)
    asyncio.run(scheduler.weekly_smoke_test_job())


def test_start_and_shutdown_scheduler():
    from app import scheduler

    async def _run():
        sched = scheduler.start_scheduler()
        assert sched is not None
        assert sched.running
        # idempotent: tekrar çağrı aynı örneği döner
        again = scheduler.start_scheduler()
        assert again is sched
        job_ids = {j.id for j in sched.get_jobs()}
        assert "nightly_batch" in job_ids
        assert "k2_batch" in job_ids
        assert "fetch_investment_prices" in job_ids
        assert "weekly_smoke_test" in job_ids
        scheduler.shutdown_scheduler()
        assert scheduler._scheduler is None

    asyncio.run(_run())


def test_trigger_after_action_resolution_swallows(db_session, test_user, monkeypatch):
    from app import scheduler
    monkeypatch.setattr(scheduler, "extract_action_rejection_pattern",
                        lambda db, uid: (_ for _ in ()).throw(RuntimeError("arp fail")))
    # exception sızmamalı
    scheduler.trigger_after_action_resolution(db_session, test_user.id)


def test_trigger_after_user_message_swallows_decision_rhythm(db_session, test_user, monkeypatch):
    from app import scheduler
    monkeypatch.setattr(scheduler, "extract_decision_rhythm",
                        lambda db, uid: (_ for _ in ()).throw(RuntimeError("dr fail")))
    scheduler.trigger_after_user_message(db_session, test_user.id)


# ============================================================
# COACH — pure helper'lar (GERÇEK LLM YOK)
# ============================================================

class _FakeProvider:
    NAME = "Fake"
    model = "fake-model"

    def __init__(self, text="ok"):
        self._text = text

    def chat(self, system_prompt, messages, tools=None):
        from app.coach import LLMResponse
        return LLMResponse(text=self._text, tool_calls=[])


@pytest.mark.parametrize("msg,expected", [
    ("Bugün ne yapmalıyım?", True),
    ("Bu iyi mi", True),
    ("Nasıl bir strateji izlemeliyim", True),
    ("Durumumu değerlendir", True),
    ("Portföyümü analiz et", True),
    ("500 lira harcadım", False),
    ("Maaşı aldım bugün", False),
    # M88 mutasyon-testi boşluğu: SADECE '?' ile soru (başka anahtar kelime YOK) — '?' dalı
    # kaldırılırsa bu vaka False dönerdi (mutant kaçmıştı, bu satır onu öldürür).
    ("Faturayı ödedim?", True),
    ("Enparadan çektim?", True),
])
def test_is_question(msg, expected):
    from app.coach import is_question
    assert is_question(msg) is expected


@pytest.mark.parametrize("text,expected", [
    ("Cevap [CONFIDENCE: 0.85]", 0.85),
    ("[Confidence: 85]", 0.85),
    ("confidence=0.7 son", 0.7),
    ("[CONFIDENCE: 200]", None),   # >100 invalid
    ("[CONFIDENCE: abc]", None),   # non-numeric
    ("hiç güven yok", None),
    ("ilk [CONFIDENCE: 0.3] son [CONFIDENCE: 0.9]", 0.9),  # son match
])
def test_parse_confidence(text, expected):
    from app.coach import _parse_confidence
    assert _parse_confidence(text) == expected


def test_parse_confidence_empty():
    from app.coach import _parse_confidence
    assert _parse_confidence("") is None


def test_is_request_too_large_keyword():
    from app.coach import _is_request_too_large
    assert _is_request_too_large(Exception("Request too large for model")) is True
    assert _is_request_too_large(Exception("context length exceeded")) is True
    assert _is_request_too_large(Exception("random error")) is False


def test_is_request_too_large_status_code():
    from app.coach import _is_request_too_large

    class _Exc(Exception):
        status_code = 413

    assert _is_request_too_large(_Exc("boom")) is True


def test_trim_history_under_limit_unchanged():
    from app.coach import _trim_history_to_size
    msgs = [{"role": "user", "content": "kısa"}]
    assert _trim_history_to_size(msgs) == msgs


def test_trim_history_over_limit_drops_oldest():
    from app.coach import _trim_history_to_size, MAX_TOTAL_HISTORY_CHARS
    big = "x" * 2000
    msgs = [{"role": "user", "content": big} for _ in range(5)]
    trimmed = _trim_history_to_size(msgs)
    total = sum(len(m["content"]) for m in trimmed)
    assert total <= MAX_TOTAL_HISTORY_CHARS or len(trimmed) == 1
    assert len(trimmed) < 5


def test_truncate_long_message_assistant():
    from app.coach import _truncate_long_message, MAX_HISTORY_MESSAGE_CHARS
    long = "a" * (MAX_HISTORY_MESSAGE_CHARS + 500)
    out = _truncate_long_message(long, "assistant")
    assert "ortasi ozetlendi" in out
    assert len(out) < len(long)


def test_truncate_long_message_user_untouched():
    from app.coach import _truncate_long_message
    long = "a" * 5000
    assert _truncate_long_message(long, "user") == long


def test_postprocess_report_strips_emanet_when_zero():
    from app.coach import _postprocess_report
    text = (
        "## 4. Genel Durum\nİyi.\n\n"
        "## 5. Emanet Kasa\nEmanet 1000 TL.\n\n"
        "## 6. Sonuç\nBitti."
    )
    out = _postprocess_report(text, {"emanet_kasa": 0}, "durum")
    assert "Emanet 1000" not in out
    assert "Genel Durum" in out
    assert "Sonuç" in out


def test_postprocess_report_removes_fake_confirmation():
    from app.coach import _postprocess_report
    text = "[500 TL gider kaydedildi]"
    out = _postprocess_report(text, {"emanet_kasa": 0}, "harcadım", proposed_actions=[])
    assert "kaydedildi" not in out
    assert "Hangi hesaptan" in out  # clarify mesajı eklendi


def test_postprocess_report_keeps_when_action_proposed():
    from app.coach import _postprocess_report
    text = "[500 TL gider kaydedildi]"
    out = _postprocess_report(text, {"emanet_kasa": 0}, "harcadım",
                              proposed_actions=[{"x": 1}])
    # aksiyon önerildi → sahte-tamamlama temizliği çalışmaz
    assert "kaydedildi" in out


def test_postprocess_report_empty():
    from app.coach import _postprocess_report
    assert _postprocess_report("", {}, "") == ""


def test_build_smart_reply_variants():
    from app.coach import _build_smart_reply
    assert _build_smart_reply("dolu metin", []) == "dolu metin"
    assert "bir aksiyon" in _build_smart_reply("", [{"a": 1}])
    assert "2 aksiyon" in _build_smart_reply("", [{"a": 1}, {"b": 2}])
    assert "tekrar" in _build_smart_reply("", [])


def test_build_provider_unknown_raises(monkeypatch):
    from app.coach import build_provider
    monkeypatch.setenv("LLM_PROVIDER", "martian")
    with pytest.raises(ValueError, match="Bilinmeyen LLM_PROVIDER"):
        build_provider()


def test_build_provider_anthropic_no_key_raises(monkeypatch):
    from app.coach import build_provider
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_provider()


def test_build_provider_gemini_no_key_raises(monkeypatch):
    from app.coach import build_provider
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_provider()


def test_build_provider_ollama(monkeypatch):
    from app.coach import build_provider, OllamaProvider
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    p = build_provider()
    assert isinstance(p, OllamaProvider)


def test_build_provider_fallback_single(monkeypatch):
    """Fallback ama tek provider key'i → o provider tek modda döner."""
    import app.coach as coach
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    fake = _FakeProvider()
    monkeypatch.setattr(coach, "_build_gemini", lambda: fake)
    for name in ["_build_openrouter", "_build_cerebras", "_build_together",
                 "_build_deepinfra", "_build_groq", "_build_ollama"]:
        monkeypatch.setattr(coach, name, lambda: None)
    p = coach.build_provider()
    assert p is fake


def test_build_provider_fallback_chain(monkeypatch):
    from app.coach import FallbackProvider
    import app.coach as coach
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    monkeypatch.setattr(coach, "_build_gemini", lambda: _FakeProvider("G"))
    monkeypatch.setattr(coach, "_build_groq", lambda: _FakeProvider("Q"))
    for name in ["_build_openrouter", "_build_cerebras", "_build_together",
                 "_build_deepinfra", "_build_ollama"]:
        monkeypatch.setattr(coach, name, lambda: None)
    p = coach.build_provider()
    assert isinstance(p, FallbackProvider)


def test_build_provider_fallback_no_keys_raises(monkeypatch):
    import app.coach as coach
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    for name in ["_build_gemini", "_build_openrouter", "_build_cerebras",
                 "_build_together", "_build_deepinfra", "_build_groq", "_build_ollama"]:
        monkeypatch.setattr(coach, name, lambda: None)
    with pytest.raises(ValueError, match="hicbir provider"):
        coach.build_provider()


# ============================================================
# FUND_TRACKER
# ============================================================

def test_get_freshness_summary_counts(db_session, test_user):
    from app.fund_tracker import get_freshness_summary
    # stale (eski fiyat, emanet değil) + never_set + emanet(stale ama sayılmaz)
    db_session.add_all([
        Account(user_id=test_user.id, name="Stale Fon", account_type=AccountType.investment,
                fund_code="STL", last_price_update=datetime.utcnow() - timedelta(days=5)),
        Account(user_id=test_user.id, name="Yeni Fon", account_type=AccountType.investment,
                fund_code="NEW", last_price_update=None),
        Account(user_id=test_user.id, name="Emanet Fon", account_type=AccountType.investment,
                fund_code="EMN", is_emanet=True,
                last_price_update=datetime.utcnow() - timedelta(days=5)),
    ])
    db_session.commit()
    summary = get_freshness_summary(db_session, test_user.id)
    assert summary["total_investments"] == 3
    # Stale Fon + Yeni Fon(None da stale) sayılır; Emanet Fon stale ama sayılmaz
    assert summary["stale_count"] == 2
    assert summary["never_set_count"] == 1
    assert len(summary["items"]) == 3


def _install_fake_pytefas(monkeypatch, fetch_impl):
    """Sahte pytefas modülü — try_auto_fetch_fund_price'ın import'unu karşılar."""
    mod = types.ModuleType("pytefas")

    class TefasAPIError(Exception):
        pass

    class TefasRateLimitError(Exception):
        pass

    class TefasInvalidParameterError(Exception):
        pass

    class _DF:
        def __init__(self, rows):
            self._rows = rows

        @property
        def empty(self):
            return not self._rows

        @property
        def iloc(self):
            rows = self._rows
            class _ILoc:
                def __getitem__(self, idx):
                    return rows[idx]
            return _ILoc()

    class Crawler:
        def fetch(self, date_str, kind, fund_code, columns):
            return fetch_impl(date_str, kind, fund_code, _DF)

    mod.Crawler = Crawler
    mod.TefasAPIError = TefasAPIError
    mod.TefasRateLimitError = TefasRateLimitError
    mod.TefasInvalidParameterError = TefasInvalidParameterError
    monkeypatch.setitem(sys.modules, "pytefas", mod)
    return mod


def test_try_auto_fetch_empty_code():
    from app.fund_tracker import try_auto_fetch_fund_price
    assert try_auto_fetch_fund_price("") is None


def test_try_auto_fetch_success_yat(monkeypatch):
    from app.fund_tracker import try_auto_fetch_fund_price

    def fetch(date_str, kind, fund_code, DF):
        assert kind == "YAT"
        return DF([{"price": 12.3456}])

    _install_fake_pytefas(monkeypatch, fetch)
    price = try_auto_fetch_fund_price("TLY")
    assert price == Decimal("12.3456")


def test_try_auto_fetch_emk_fallback(monkeypatch):
    from app.fund_tracker import try_auto_fetch_fund_price

    def fetch(date_str, kind, fund_code, DF):
        mod = sys.modules["pytefas"]
        if kind == "YAT":
            raise mod.TefasInvalidParameterError("emeklilik fonu")
        return DF([{"price": 5.0}])   # EMK başarılı

    _install_fake_pytefas(monkeypatch, fetch)
    price = try_auto_fetch_fund_price("EMK1")
    assert price == Decimal("5.0000")


def test_try_auto_fetch_all_empty_returns_none(monkeypatch):
    from app.fund_tracker import try_auto_fetch_fund_price

    def fetch(date_str, kind, fund_code, DF):
        return DF([])   # her gün boş

    _install_fake_pytefas(monkeypatch, fetch)
    assert try_auto_fetch_fund_price("ZZZ") is None


def test_try_auto_fetch_outer_exception_returns_none(monkeypatch):
    """pytefas import edilemezse (yok) None döner (dış try/except)."""
    from app.fund_tracker import try_auto_fetch_fund_price
    monkeypatch.setitem(sys.modules, "pytefas", None)  # import ederse ImportError
    assert try_auto_fetch_fund_price("ABC") is None


def test_try_auto_fetch_stock_erisilemezse_none(monkeypatch):
    """M-hisse (Wave-7): artık STUB değil — İş Yatırım fetch'i. Endpoint erişilemezse None döner.
    (Gerçek parse/çekim testleri: tests/test_stock_price_isyatirim_m_hisse.py — canlı+mock.)"""
    def _boom(*a, **k):
        raise OSError("network yok")
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    from app.fund_tracker import try_auto_fetch_stock_price
    assert try_auto_fetch_stock_price("THYAO") is None


def test_update_fund_price_manual_success(db_session, test_user):
    from app.fund_tracker import update_fund_price_manual
    acc = Account(user_id=test_user.id, name="Fon", account_type=AccountType.investment,
                  fund_code="TLY", lot_count=10, current_price=Decimal("100"))
    db_session.add(acc)
    db_session.commit()
    res = update_fund_price_manual(db_session, acc.id, 150.0, user_id=test_user.id)
    assert res["success"] is True
    assert res["new_price"] == 150.0
    assert float(res["new_value"]) == pytest.approx(1500.0)


def test_update_fund_price_manual_not_found(db_session, test_user):
    from app.fund_tracker import update_fund_price_manual
    res = update_fund_price_manual(db_session, 9999, 100.0)
    assert res["success"] is False
    assert "bulunamadi" in res["message"]


def test_update_fund_price_manual_not_investment(db_session, test_user):
    from app.fund_tracker import update_fund_price_manual
    acc = Account(user_id=test_user.id, name="Kasa", account_type=AccountType.cash, balance=50.0)
    db_session.add(acc)
    db_session.commit()
    res = update_fund_price_manual(db_session, acc.id, 100.0)
    assert res["success"] is False
    assert "yatirim hesabi degil" in res["message"]


def test_update_fund_price_manual_nonpositive(db_session, test_user):
    from app.fund_tracker import update_fund_price_manual
    acc = Account(user_id=test_user.id, name="Fon", account_type=AccountType.investment,
                  fund_code="TLY", lot_count=5)
    db_session.add(acc)
    db_session.commit()
    res = update_fund_price_manual(db_session, acc.id, 0.0)
    assert res["success"] is False
    assert "sifirdan buyuk" in res["message"]


# ============================================================
# OAUTH — exchange_code dalları (OAuth2Session mock)
# ============================================================

class _FakeResp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class _FakeOAuthSession:
    """OAuth2Session mock — fetch_token + get zincirini kontrol eder."""
    def __init__(self, *a, **k):
        pass

    # sınıf-seviye script (test her seferinde ayarlar)
    token = {"access_token": "tok"}
    get_map: dict = {}

    def fetch_token(self, *a, **k):
        return type(self).token

    def get(self, url, **k):
        return _FakeResp(type(self).get_map.get(url, {}))

    def create_authorization_url(self, url, state=None, **k):
        return (f"{url}?state={state}", state)


def test_provider_configured_unknown():
    from app.services import oauth
    assert oauth.provider_configured("bilinmeyen") is False


def test_provider_configured_true(monkeypatch):
    from app.services import oauth
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "sec")
    assert oauth.provider_configured("google") is True


def test_prune_states_removes_expired():
    from app.services import oauth
    oauth._states.clear()
    oauth._states["expired"] = 0.0   # çok eski (1970)
    oauth._states["fresh"] = __import__("time").time()
    oauth._prune_states()
    assert "expired" not in oauth._states
    assert "fresh" in oauth._states
    oauth._states.clear()


def test_get_auth_url(monkeypatch):
    from app.services import oauth
    monkeypatch.setattr(oauth, "OAuth2Session", _FakeOAuthSession)
    url = oauth.get_auth_url("google", "state123")
    assert "state123" in url


def test_exchange_code_google_success(monkeypatch):
    from app.services import oauth
    _FakeOAuthSession.token = {"access_token": "tok"}
    _FakeOAuthSession.get_map = {
        oauth._PROVIDERS["google"]["userinfo_url"]:
            {"sub": "123", "email": "USER@Example.com", "email_verified": True, "name": "Ali"},
    }
    monkeypatch.setattr(oauth, "OAuth2Session", _FakeOAuthSession)
    res = oauth.exchange_code("google", "code123")
    assert res == {"provider": "google", "sub": "123", "email": "user@example.com", "name": "Ali"}


def test_exchange_code_no_access_token(monkeypatch):
    from app.services import oauth
    _FakeOAuthSession.token = {}
    monkeypatch.setattr(oauth, "OAuth2Session", _FakeOAuthSession)
    with pytest.raises(ValueError, match="access_token"):
        oauth.exchange_code("google", "code")


def test_exchange_code_google_unverified_email(monkeypatch):
    from app.services import oauth
    _FakeOAuthSession.token = {"access_token": "tok"}
    _FakeOAuthSession.get_map = {
        oauth._PROVIDERS["google"]["userinfo_url"]:
            {"sub": "1", "email": "u@e.com", "email_verified": False},
    }
    monkeypatch.setattr(oauth, "OAuth2Session", _FakeOAuthSession)
    with pytest.raises(ValueError, match="doğrulanmış e-posta"):
        oauth.exchange_code("google", "code")


def test_exchange_code_github_email_from_emails_endpoint(monkeypatch):
    from app.services import oauth
    _FakeOAuthSession.token = {"access_token": "tok"}
    _FakeOAuthSession.get_map = {
        oauth._PROVIDERS["github"]["userinfo_url"]:
            {"id": 42, "email": None, "login": "ghuser", "name": "GH User"},
        oauth._PROVIDERS["github"]["emails_url"]:
            [{"email": "primary@gh.com", "primary": True, "verified": True}],
    }
    monkeypatch.setattr(oauth, "OAuth2Session", _FakeOAuthSession)
    res = oauth.exchange_code("github", "code")
    assert res["email"] == "primary@gh.com"
    assert res["provider"] == "github"
    assert res["sub"] == "42"


def test_exchange_code_github_no_email_raises(monkeypatch):
    from app.services import oauth
    _FakeOAuthSession.token = {"access_token": "tok"}
    _FakeOAuthSession.get_map = {
        oauth._PROVIDERS["github"]["userinfo_url"]:
            {"id": 1, "email": None, "login": "x"},
        oauth._PROVIDERS["github"]["emails_url"]: [],
    }
    monkeypatch.setattr(oauth, "OAuth2Session", _FakeOAuthSession)
    with pytest.raises(ValueError, match="doğrulanmış e-posta"):
        oauth.exchange_code("github", "code")


# ============================================================
# WORKSPACE_INVITE
# ============================================================

def test_decode_invite_token_wrong_type(monkeypatch):
    import jwt
    from app.services import workspace_invite as wi
    from app.auth import _secret, _ALGO
    bad = jwt.encode({"type": "not_invite", "workspace_id": 1, "email": "a@b.com",
                      "role": "viewer"}, _secret(), algorithm=_ALGO)
    with pytest.raises(jwt.InvalidTokenError):
        wi.decode_invite_token(bad)


def test_create_and_decode_invite_roundtrip():
    from app.services import workspace_invite as wi
    tok = wi.create_invite_token(7, "Test@Example.com", WorkspaceRole.editor)
    decoded = wi.decode_invite_token(tok)
    assert decoded["workspace_id"] == 7
    assert decoded["email"] == "test@example.com"
    assert decoded["role"] == WorkspaceRole.editor


def test_build_invite_link(monkeypatch):
    from app.services import workspace_invite as wi
    monkeypatch.setenv("FRONTEND_URL", "https://app.example.com/")
    link = wi.build_invite_link("abc")
    assert link == "https://app.example.com/workspaces/join?token=abc"


def test_send_invite_email_success(monkeypatch):
    from app.services import workspace_invite as wi
    import app.services.email as email_mod
    captured = {}

    def fake_send(to, subject, text, html):
        captured["to"] = to
        captured["subject"] = subject
        return True

    monkeypatch.setattr(email_mod, "send_email", fake_send)
    ok = wi.send_invite_email("a@b.com", "Aile", WorkspaceRole.viewer, "http://link")
    assert ok is True
    assert captured["to"] == "a@b.com"
    assert "Aile" in captured["subject"]


def test_send_invite_email_smtp_unconfigured(monkeypatch):
    from app.services import workspace_invite as wi
    import app.services.email as email_mod
    monkeypatch.setattr(email_mod, "send_email", lambda *a, **k: False)
    assert wi.send_invite_email("a@b.com", "Aile", WorkspaceRole.owner, "http://link") is False


# ============================================================
# WORKSPACE_DEPS — fail-fast + require_write dalları
# ============================================================

def test_get_active_membership_no_personal_ws_404(db_session, test_user):
    from app.workspace_deps import get_active_membership
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        get_active_membership(x_workspace_id=None, user=test_user, db=db_session)
    assert exc.value.status_code == 404


def test_get_active_membership_not_member_403(db_session, test_user):
    from app.workspace_deps import get_active_membership
    from fastapi import HTTPException
    ws = Workspace(owner_user_id=test_user.id, name="Kişisel", is_personal=True)
    db_session.add(ws)
    db_session.commit()
    # personal ws var ama membership yok
    with pytest.raises(HTTPException) as exc:
        get_active_membership(x_workspace_id=None, user=test_user, db=db_session)
    assert exc.value.status_code == 403


def test_get_active_membership_returns_membership(db_session, test_user):
    from app.workspace_deps import get_active_membership
    ws = Workspace(owner_user_id=test_user.id, name="Kişisel", is_personal=True)
    db_session.add(ws)
    db_session.commit()
    m = WorkspaceMembership(workspace_id=ws.id, user_id=test_user.id, role=WorkspaceRole.owner)
    db_session.add(m)
    db_session.commit()
    result = get_active_membership(x_workspace_id=None, user=test_user, db=db_session)
    assert result.id == m.id


class _FakeRequest:
    def __init__(self, method):
        self.method = method


def test_require_write_get_method_passes(db_session, test_user):
    from app.workspace_deps import require_write
    dep = require_write()
    # GET → izin kontrolü yok
    assert dep(_FakeRequest("GET"), x_workspace_id=None, user=test_user, db=db_session) is None


def test_require_write_no_workspace_passes(db_session, test_user):
    from app.workspace_deps import require_write
    dep = require_write()
    # POST ama personal ws yok → köprü: izin atlanır (153)
    assert dep(_FakeRequest("POST"), x_workspace_id=None, user=test_user, db=db_session) is None


def test_require_write_viewer_denied(db_session, test_user):
    from app.workspace_deps import require_write
    from fastapi import HTTPException
    ws = Workspace(owner_user_id=test_user.id, name="Kişisel", is_personal=True)
    db_session.add(ws)
    db_session.commit()
    db_session.add(WorkspaceMembership(workspace_id=ws.id, user_id=test_user.id,
                                       role=WorkspaceRole.viewer))
    db_session.commit()
    dep = require_write()
    with pytest.raises(HTTPException) as exc:
        dep(_FakeRequest("POST"), x_workspace_id=None, user=test_user, db=db_session)
    assert exc.value.status_code == 403


def test_require_write_editor_passes(db_session, test_user):
    from app.workspace_deps import require_write
    ws = Workspace(owner_user_id=test_user.id, name="Kişisel", is_personal=True)
    db_session.add(ws)
    db_session.commit()
    db_session.add(WorkspaceMembership(workspace_id=ws.id, user_id=test_user.id,
                                       role=WorkspaceRole.editor))
    db_session.commit()
    dep = require_write()
    assert dep(_FakeRequest("POST"), x_workspace_id=None, user=test_user, db=db_session) is None


def test_require_write_not_member_403(db_session, test_user):
    from app.workspace_deps import require_write
    from fastapi import HTTPException
    dep = require_write()
    # header ile workspace verildi ama üye değil (159)
    with pytest.raises(HTTPException) as exc:
        dep(_FakeRequest("POST"), x_workspace_id=999, user=test_user, db=db_session)
    assert exc.value.status_code == 403
