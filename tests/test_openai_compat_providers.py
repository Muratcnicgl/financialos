"""
OpenAI-uyumlu LLM sağlayıcıları (Cerebras, OpenRouter) — paylaşılan _raw_chat sözleşmesi.
Ollama'nın kendi testi var; bu ikisi aynı deseni (OpenAI client + tool mapping + tool_call
parse) paylaşır. openai.OpenAI mock — gerçek ağ yok. Fallback zinciri sözleşmesini kilitler.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.coach import CerebrasProvider, OpenRouterProvider


class _FakeCompletions:
    def __init__(self, message):
        self._message = message
        self.captured = None

    def create(self, **kwargs):
        self.captured = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=self._message)])


def _patch_openai(monkeypatch, message):
    completions = _FakeCompletions(message)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    return completions


PROVIDERS = [
    (CerebrasProvider, "Cerebras"),
    (OpenRouterProvider, "OpenRouter"),
]


@pytest.mark.parametrize("cls,name", PROVIDERS)
def test_metin_yaniti_parse(monkeypatch, cls, name):
    msg = SimpleNamespace(content="Kart borcun 42.100 TL.", tool_calls=None)
    _patch_openai(monkeypatch, msg)
    p = cls(api_key="test-key")
    assert p.NAME == name
    resp = p._raw_chat("sys", [{"role": "user", "content": "durum"}], tools=[])
    assert resp.text == "Kart borcun 42.100 TL."
    assert resp.tool_calls == []


@pytest.mark.parametrize("cls,name", PROVIDERS)
def test_tool_call_parse(monkeypatch, cls, name):
    tc = SimpleNamespace(function=SimpleNamespace(
        name="propose_action", arguments='{"amount": 250, "category": "market"}'))
    msg = SimpleNamespace(content="", tool_calls=[tc])
    _patch_openai(monkeypatch, msg)
    p = cls(api_key="test-key")
    resp = p._raw_chat("sys", [{"role": "user", "content": "market 250"}],
                       tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0]["name"] == "propose_action"
    assert resp.tool_calls[0]["input"] == {"amount": 250, "category": "market"}


@pytest.mark.parametrize("cls,name", PROVIDERS)
def test_bozuk_arguments_bos_dict(monkeypatch, cls, name):
    tc = SimpleNamespace(function=SimpleNamespace(name="propose_action", arguments="{bozuk"))
    msg = SimpleNamespace(content="", tool_calls=[tc])
    _patch_openai(monkeypatch, msg)
    p = cls(api_key="test-key")
    resp = p._raw_chat("sys", [{"role": "user", "content": "x"}],
                       tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert resp.tool_calls[0]["input"] == {}


@pytest.mark.parametrize("cls,name", PROVIDERS)
def test_tools_kwargs_iletiliyor(monkeypatch, cls, name):
    """tools verilince create'e tools + tool_choice=auto geçilir."""
    msg = SimpleNamespace(content="ok", tool_calls=None)
    comp = _patch_openai(monkeypatch, msg)
    p = cls(api_key="test-key")
    p._raw_chat("sys", [{"role": "user", "content": "x"}],
                tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert comp.captured.get("tool_choice") == "auto"
    assert "tools" in comp.captured
