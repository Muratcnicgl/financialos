"""
LLM-007 — usage/provider_used/model_name YALNIZ Groq'ta değil, TÜM sağlayıcılarda set edilir.
Trace + maliyet takibi gerçek sağlayıcı (Gemini/Cerebras/...) için de dolu olmalı.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.coach import _openai_compat_usage


def test_openai_compat_usage_helper():
    resp = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=120, completion_tokens=45))
    assert _openai_compat_usage(resp) == {"input_tokens": 120, "output_tokens": 45}
    assert _openai_compat_usage(SimpleNamespace(usage=None)) is None
    assert _openai_compat_usage(SimpleNamespace()) is None


class _FakeCompletions:
    def __init__(self, message, usage):
        self._m = message; self._u = usage
    def create(self, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=self._m)], usage=self._u)


def _fake_client(message, usage):
    return SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions(message, usage)))


@pytest.mark.parametrize("cls_name,expected_name", [
    ("CerebrasProvider", "cerebras"),
    ("OpenRouterProvider", "openrouter"),
])
def test_openai_compat_provider_metadata(cls_name, expected_name):
    pytest.importorskip("openai")
    import app.coach as c
    cls = getattr(c, cls_name)
    p = cls(api_key="k")
    msg = SimpleNamespace(content="ok", tool_calls=None)
    p.client = _fake_client(msg, SimpleNamespace(prompt_tokens=10, completion_tokens=5))
    resp = p._raw_chat("sys", [{"role": "user", "content": "x"}], tools=[])
    assert resp.model_name == p.model            # LLM-007: model_name set
    assert resp.provider_used == expected_name    # gerçek sağlayıcı adı
    assert resp.usage == {"input_tokens": 10, "output_tokens": 5}
