"""
Koç geçmiş-yönetimi saf fonksiyonları — BUG #019 (trim) + #036 (tool-aware/orphan).
Bunlar deterministik ve LLM-mesaj-protokolü açısından kritik (OpenAI: orphan tool mesajı = 400).
"""
from __future__ import annotations

import json

from app.coach import (
    _to_openai_messages, _truncate_long_message, _trim_history_to_size,
    MAX_HISTORY_MESSAGE_CHARS, MAX_TOTAL_HISTORY_CHARS,
)


# ============================================================
# _to_openai_messages — tool-aware + orphan koruması (#036)
# ============================================================

def test_orphan_tool_mesaji_atlanir():
    """Eşleşen assistant tool_call'u OLMAYAN tool mesajı düşürülür (OpenAI 400 önlemi)."""
    msgs = [
        {"role": "user", "content": "merhaba"},
        {"role": "tool", "tool_call_id": "call_yok", "content": "orphan sonuc"},
    ]
    out = _to_openai_messages(msgs)
    assert all(m["role"] != "tool" for m in out)


def test_gecerli_tool_mesaji_korunur():
    tc_json = json.dumps([{"id": "call_1", "name": "propose_action", "args": {"x": 1}}])
    msgs = [
        {"role": "assistant", "content": "kaydediyorum", "tool_calls_json": tc_json},
        {"role": "tool", "tool_call_id": "call_1", "content": "action_id=5"},
    ]
    out = _to_openai_messages(msgs)
    # assistant tool_calls üretti + tool mesajı korundu
    asst = [m for m in out if m["role"] == "assistant"][0]
    assert asst["tool_calls"][0]["id"] == "call_1"
    assert asst["tool_calls"][0]["function"]["name"] == "propose_action"
    tool = [m for m in out if m["role"] == "tool"][0]
    assert tool["tool_call_id"] == "call_1"


def test_invariant_hicbir_orphan_tool_output_ta_kalmaz():
    """INVARIANT: çıktıdaki her tool mesajının tool_call_id'si bir assistant tool_call'unda olmalı."""
    tc_json = json.dumps([{"id": "call_A", "name": "propose_action", "args": {}}])
    msgs = [
        {"role": "assistant", "content": "", "tool_calls_json": tc_json},
        {"role": "tool", "tool_call_id": "call_A", "content": "ok"},
        {"role": "tool", "tool_call_id": "call_ORPHAN", "content": "kotu"},
        {"role": "user", "content": "devam"},
    ]
    out = _to_openai_messages(msgs)
    valid_ids = set()
    for m in out:
        if m["role"] == "assistant":
            for tc in m.get("tool_calls", []):
                valid_ids.add(tc["id"])
    for m in out:
        if m["role"] == "tool":
            assert m["tool_call_id"] in valid_ids


def test_bozuk_tool_calls_json_crash_etmez():
    msgs = [{"role": "assistant", "content": "x", "tool_calls_json": "{bozuk"}]
    out = _to_openai_messages(msgs)                 # crash olmamalı
    assert out[0]["role"] == "assistant"
    assert "tool_calls" not in out[0]               # bozuk → tool_calls yok


def test_duz_mesajlar_passthrough():
    msgs = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    out = _to_openai_messages(msgs)
    assert out == [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]


# ============================================================
# _truncate_long_message (#019)
# ============================================================

def test_truncate_kisa_assistant_degismez():
    c = "kısa cevap"
    assert _truncate_long_message(c, "assistant") == c


def test_truncate_uzun_assistant_kisalir():
    c = "A" * (MAX_HISTORY_MESSAGE_CHARS + 500)
    out = _truncate_long_message(c, "assistant")
    assert len(out) < len(c)
    assert "ozetlendi" in out


def test_truncate_user_degismez_uzun_olsa_bile():
    c = "B" * (MAX_HISTORY_MESSAGE_CHARS + 500)
    assert _truncate_long_message(c, "user") == c   # yalnız assistant kısaltılır


# ============================================================
# _trim_history_to_size (#019)
# ============================================================

def test_trim_limit_altinda_degismez():
    msgs = [{"role": "user", "content": "x" * 100}]
    assert _trim_history_to_size(list(msgs)) == msgs


def test_trim_limit_ustunde_eskiyi_atar_ve_bosaltmaz():
    # 5 mesaj, her biri 2000 char = 10000 > 6000
    msgs = [{"role": "user", "content": f"{i}" * 2000} for i in range(5)]
    out = _trim_history_to_size(list(msgs))
    total = sum(len(m["content"]) for m in out)
    assert total <= MAX_TOTAL_HISTORY_CHARS or len(out) == 1
    assert len(out) >= 1                             # asla boşalmaz
    # en yeni korunur (son mesaj)
    assert out[-1]["content"].startswith("4")
