"""
AnthropicProvider _raw_chat sözleşme kilidi (sağlayıcı setini tamamlar). anthropic SDK mock.
"""
from __future__ import annotations

import sys
import types as pytypes
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.coach import AnthropicProvider


def _patch_anthropic(monkeypatch, content_blocks):
    resp = SimpleNamespace(content=content_blocks)
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=MagicMock(return_value=resp)))
    fake_mod = pytypes.ModuleType("anthropic")
    fake_mod.Anthropic = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)
    return fake_client


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool_use(name, inp):
    return SimpleNamespace(type="tool_use", name=name, input=inp)


def test_metin_parse(monkeypatch):
    _patch_anthropic(monkeypatch, [_text("Kart borcun 42.100 TL.")])
    p = AnthropicProvider(api_key="k")
    assert p.NAME == "Anthropic"
    resp = p._raw_chat("sys", [{"role": "user", "content": "durum"}], tools=[])
    assert resp.text == "Kart borcun 42.100 TL."
    assert resp.tool_calls == []


def test_tool_use_parse(monkeypatch):
    _patch_anthropic(monkeypatch, [_tool_use("propose_action", {"amount": 250})])
    p = AnthropicProvider(api_key="k")
    resp = p._raw_chat("sys", [{"role": "user", "content": "market 250"}],
                       tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert resp.tool_calls[0]["name"] == "propose_action"
    assert resp.tool_calls[0]["input"] == {"amount": 250}


def test_karma_text_ve_tool(monkeypatch):
    _patch_anthropic(monkeypatch, [_text("Kaydediyorum."), _tool_use("propose_action", {"x": 1})])
    p = AnthropicProvider(api_key="k")
    resp = p._raw_chat("sys", [{"role": "user", "content": "x"}],
                       tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert resp.text == "Kaydediyorum."
    assert len(resp.tool_calls) == 1
