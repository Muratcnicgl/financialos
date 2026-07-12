"""
OllamaProvider (LLM-005 / DEVRİMSEL #2) birim testleri.

Gerçek Ollama gerektirmez: openai.OpenAI mock'lanır. Kök vizyon "Sovereign OS" —
tamamen yerel/egemen LLM sağlayıcı; fallback zincirinin son halkası.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.coach import OllamaProvider, _build_ollama, build_provider, FallbackProvider


class _FakeCompletions:
    def __init__(self, message):
        self._message = message
        self.captured_kwargs = None

    def create(self, **kwargs):
        self.captured_kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=self._message)])


def _patch_openai(monkeypatch, message):
    """openai.OpenAI'ı, verilen message'ı dönen sahte client ile değiştir."""
    completions = _FakeCompletions(message)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    return fake_openai, completions


def test_metin_yaniti_parse(monkeypatch):
    msg = SimpleNamespace(content="Kart borcun 42.100 TL.", tool_calls=None)
    _patch_openai(monkeypatch, msg)

    p = OllamaProvider()
    resp = p._raw_chat("sys", [{"role": "user", "content": "durum"}], tools=[])

    assert resp.text == "Kart borcun 42.100 TL."
    assert resp.tool_calls == []


def test_tool_call_parse(monkeypatch):
    tc = SimpleNamespace(
        function=SimpleNamespace(name="propose_action", arguments='{"amount": 250, "category": "market"}')
    )
    msg = SimpleNamespace(content="", tool_calls=[tc])
    _patch_openai(monkeypatch, msg)

    p = OllamaProvider()
    resp = p._raw_chat("sys", [{"role": "user", "content": "market 250"}],
                       tools=[{"name": "propose_action", "description": "d", "parameters": {}}])

    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0]["name"] == "propose_action"
    assert resp.tool_calls[0]["input"] == {"amount": 250, "category": "market"}


def test_bozuk_tool_arguments_bos_dict(monkeypatch):
    tc = SimpleNamespace(function=SimpleNamespace(name="propose_action", arguments="{bozuk json"))
    msg = SimpleNamespace(content="", tool_calls=[tc])
    _patch_openai(monkeypatch, msg)

    p = OllamaProvider()
    resp = p._raw_chat("sys", [{"role": "user", "content": "x"}],
                       tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert resp.tool_calls[0]["input"] == {}


def test_default_base_url_ve_model(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    msg = SimpleNamespace(content="", tool_calls=None)
    _patch_openai(monkeypatch, msg)

    p = OllamaProvider()
    assert p.base_url == "http://localhost:11434/v1"
    assert p.model == "qwen2.5:7b-instruct"


def test_env_override_base_url_ve_model(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://192.168.1.5:11434/v1")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:14b-instruct")
    msg = SimpleNamespace(content="", tool_calls=None)
    _patch_openai(monkeypatch, msg)

    p = OllamaProvider()
    assert p.base_url == "http://192.168.1.5:11434/v1"
    assert p.model == "qwen2.5:14b-instruct"


def test_build_ollama_kapali_ise_none(monkeypatch):
    for var in ("OLLAMA_ENABLED", "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
        monkeypatch.delenv(var, raising=False)
    assert _build_ollama() is None


def test_build_ollama_enabled_ise_provider(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    msg = SimpleNamespace(content="", tool_calls=None)
    _patch_openai(monkeypatch, msg)
    p = _build_ollama()
    assert isinstance(p, OllamaProvider)


def test_factory_ollama_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    msg = SimpleNamespace(content="", tool_calls=None)
    _patch_openai(monkeypatch, msg)
    p = build_provider()
    assert isinstance(p, OllamaProvider)


def test_fallback_zincirine_ollama_son_halka(monkeypatch):
    """OLLAMA_ENABLED + en az 1 bulut key -> fallback zinciri Ollama ile biter."""
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    for var in ("CEREBRAS_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    # Groq __init__ da openai kullanir; Ollama da. Ikisi de mock client alir.
    msg = SimpleNamespace(content="", tool_calls=None)
    _patch_openai(monkeypatch, msg)

    p = build_provider()
    assert isinstance(p, FallbackProvider)
    assert p.providers[-1].NAME == "Ollama"
