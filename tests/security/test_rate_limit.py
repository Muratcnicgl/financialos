"""M21 — auth rate limit per-bucket production değerleri."""
from __future__ import annotations

import pytest
from app import rate_limit as rl


class _Req:
    def __init__(self, ip="1.2.3.4"):
        self.client = type("C", (), {"host": ip})()


@pytest.fixture(autouse=True)
def _reset():
    rl.reset()
    yield
    rl.reset()


def test_login_default_5_15dk():
    assert rl.limit_for("login") == (5, 900)


def test_register_default_3_saat():
    assert rl.limit_for("register") == (3, 3600)


def test_oauth_default_10_dk():
    assert rl.limit_for("oauth") == (10, 60)


def test_register_4uncu_istek_429():
    req = _Req()
    for _ in range(3):
        rl.rate_limit(req, "register")  # 3 geçer
    with pytest.raises(Exception) as e:
        rl.rate_limit(req, "register")  # 4. → 429
    assert "429" in str(e.value) or "fazla" in str(e.value)


def test_farkli_ip_bagimsiz():
    for _ in range(3):
        rl.rate_limit(_Req("1.1.1.1"), "register")
    # başka IP hâlâ serbest
    rl.rate_limit(_Req("2.2.2.2"), "register")


def test_env_override(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX", "2")
    assert rl.limit_for("login")[0] == 2
