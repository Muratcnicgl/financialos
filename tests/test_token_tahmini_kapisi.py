"""
LLM-017/018 (BUG #504): token tahmini tek kaynak; geçmiş kırpımı tool çiftini yetim bırakmaz.

Ölçüm (14 Eyl 2026): `format_insights_for_prompt` `tiktoken cl100k_base` deniyordu — paket
kurulu değil (ImportError dalı hep aktifti) ve yalnız OpenAI için doğru; Türkçe'de %15 eksik
sayıyordu. Geçmiş kırpımı en eski mesajı tek tek atıyordu: asistanın tool_calls mesajı gidince
arkasındaki `tool` yanıtı yetim kalıyor, OpenAI-uyumlu sağlayıcı 400 dönüyordu. Kilitlenen:
  1. `token_tahmini` muhafazakâr (3,5 kr/token, ceil), boş 0; insights modülü onu kullanır,
     `import tiktoken` hiçbir yerde yok,
  2. kırpım sonrası geçmiş asla `tool` mesajıyla başlamaz; çift birlikte düşer,
  3. bütçe altındaki geçmişe dokunulmaz.
"""
from __future__ import annotations

from pathlib import Path

from app import coach
from app.token_tahmini import KARAKTER_BASINA_TOKEN, token_tahmini

KOK = Path(__file__).resolve().parent.parent


def test_tahmin_muhafazakar_ve_tek_kaynak():
    assert token_tahmini("") == 0 and token_tahmini(None) == 0
    assert token_tahmini("a" * 35) == 10
    assert token_tahmini("a" * 36) == 11            # ceil: aşağı yuvarlamaz
    assert KARAKTER_BASINA_TOKEN == 3.5
    ci = (KOK / "app" / "coach_insights.py").read_text(encoding="utf-8")
    assert "import tiktoken" not in ci and "from app.token_tahmini import token_tahmini as count_tokens" in ci
    assert "tiktoken" not in (KOK / "requirements.txt").read_text(encoding="utf-8")


def _uzun(n):
    return "x" * n


def test_kirpim_tool_ciftini_yetim_birakmaz():
    butce = coach.MAX_TOTAL_HISTORY_CHARS
    mesajlar = [
        {"role": "assistant", "content": _uzun(butce // 2), "tool_calls_json": "[{}]", "tool_call_id": None},
        {"role": "tool", "content": "sonuc", "tool_calls_json": None, "tool_call_id": "c1"},
        {"role": "user", "content": _uzun(butce // 2), "tool_calls_json": None, "tool_call_id": None},
        {"role": "assistant", "content": _uzun(200), "tool_calls_json": None, "tool_call_id": None},
    ]
    sonuc = coach._trim_history_to_size(list(mesajlar))
    assert sonuc[0]["role"] != "tool" and not sonuc[0].get("tool_call_id")
    assert [m["role"] for m in sonuc] == ["user", "assistant"]


def test_butce_altinda_dokunulmaz():
    mesajlar = [{"role": "user", "content": "kısa"}, {"role": "assistant", "content": "cevap"}]
    assert coach._trim_history_to_size(list(mesajlar)) == mesajlar
