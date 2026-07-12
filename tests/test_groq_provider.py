"""
GroqProvider (birincil fallback sağlayıcı) _raw_chat sözleşme kilidi. groq SDK mock — ağ yok.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.coach import GroqProvider


class _FakeCompletions:
    def __init__(self, message, usage=None):
        self._message = message
        self._usage = usage
        self.captured = None

    def create(self, **kwargs):
        self.captured = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=self._message)], usage=self._usage)


def _patch_groq(monkeypatch, message, usage=None):
    comp = _FakeCompletions(message, usage)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    fake_groq = types.ModuleType("groq")
    fake_groq.Groq = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "groq", fake_groq)
    return comp


def test_metin_parse(monkeypatch):
    msg = SimpleNamespace(content="Kart borcun 42.100 TL.", tool_calls=None)
    _patch_groq(monkeypatch, msg)
    p = GroqProvider(api_key="k")
    assert p.NAME == "Groq"
    resp = p._raw_chat("sys", [{"role": "user", "content": "durum"}], tools=[])
    assert resp.text == "Kart borcun 42.100 TL."
    assert resp.tool_calls == []


def test_tool_call_parse(monkeypatch):
    tc = SimpleNamespace(function=SimpleNamespace(
        name="propose_action", arguments='{"amount": 250}'))
    msg = SimpleNamespace(content="", tool_calls=[tc])
    _patch_groq(monkeypatch, msg)
    p = GroqProvider(api_key="k")
    resp = p._raw_chat("sys", [{"role": "user", "content": "x"}],
                       tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert resp.tool_calls[0]["name"] == "propose_action"
    assert resp.tool_calls[0]["input"] == {"amount": 250}


def test_usage_cikarilir(monkeypatch):
    msg = SimpleNamespace(content="ok", tool_calls=None)
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50)
    _patch_groq(monkeypatch, msg, usage)
    p = GroqProvider(api_key="k")
    resp = p._raw_chat("sys", [{"role": "user", "content": "x"}], tools=[])
    assert resp.usage == {"input_tokens": 100, "output_tokens": 50}


def test_bozuk_arguments_bos_dict(monkeypatch):
    tc = SimpleNamespace(function=SimpleNamespace(name="propose_action", arguments="{bozuk"))
    msg = SimpleNamespace(content="", tool_calls=[tc])
    _patch_groq(monkeypatch, msg)
    p = GroqProvider(api_key="k")
    resp = p._raw_chat("sys", [{"role": "user", "content": "x"}],
                       tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert resp.tool_calls[0]["input"] == {}
