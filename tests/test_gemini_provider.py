"""
GeminiProvider — en KARMAŞIK sağlayıcı mantığı: finish_reason → ProviderEmptyResponseError
(MALFORMED_FUNCTION_CALL/SAFETY vb. fallback tetikler). Bu mekanizma bozulursa fallback
dayanıklılığı kırılır. google.genai mock — ağ yok.
"""
from __future__ import annotations

import sys
import types as pytypes
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.coach import GeminiProvider, ProviderEmptyResponseError


# Üretim kodunun `genai_types` üzerinden kullandığı semboller — sahte modül bunları
# OTOMATİK üretir. BUG #263 dersi: liste elle tutulunca, üretimde yeni bir SDK sembolü
# (o turda `HttpOptions`) kullanmak sahteyi `AttributeError` ile kırıyor ve test, ölçmesi
# gereken fallback mantığı yerine kendi sahtesinin eksikliğini raporluyordu. Gerçek SDK
# yüzeyi ayrıca `test_kullanilan_genai_sembolleri_gercek_SDK_de_VAR` ile denetlenir.
def _install_fake_genai(monkeypatch, fake_response):
    class _SahteTypes(pytypes.ModuleType):
        def __getattr__(self, ad):   # yalnız bulunamayan adlar için çağrılır
            if ad.startswith("__"):
                raise AttributeError(ad)
            sahte = MagicMock(return_value=MagicMock())
            setattr(self, ad, sahte)   # aynı ad her seferinde aynı sahteyi versin
            return sahte

    types_mod = _SahteTypes("google.genai.types")

    genai_mod = pytypes.ModuleType("google.genai")
    genai_mod.types = types_mod
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=MagicMock(return_value=fake_response)))
    genai_mod.Client = MagicMock(return_value=fake_client)

    google_mod = pytypes.ModuleType("google")
    google_mod.genai = genai_mod
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)


def _resp(finish="STOP", parts=None, candidates_empty=False):
    if candidates_empty:
        return SimpleNamespace(candidates=[], prompt_feedback=None)
    content = SimpleNamespace(parts=parts) if parts is not None else None
    cand = SimpleNamespace(finish_reason=SimpleNamespace(name=finish),
                           content=content, safety_ratings=None)
    return SimpleNamespace(candidates=[cand], prompt_feedback=None)


def _text_part(t):
    return SimpleNamespace(text=t, function_call=None)


def _fc_part(name, args):
    return SimpleNamespace(text=None, function_call=SimpleNamespace(name=name, args=args))


def test_normal_metin(monkeypatch):
    _install_fake_genai(monkeypatch, _resp("STOP", [_text_part("Kart borcun 42.100 TL.")]))
    p = GeminiProvider(api_key="k")
    resp = p._raw_chat("sys", [{"role": "user", "content": "durum"}], tools=[])
    assert resp.text == "Kart borcun 42.100 TL."
    assert resp.tool_calls == []


def test_tool_call(monkeypatch):
    _install_fake_genai(monkeypatch, _resp("STOP", [_fc_part("propose_action", {"amount": 250})]))
    p = GeminiProvider(api_key="k")
    resp = p._raw_chat("sys", [{"role": "user", "content": "market 250"}],
                       tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert resp.tool_calls[0]["name"] == "propose_action"
    assert resp.tool_calls[0]["input"] == {"amount": 250}


def test_malformed_function_call_fallback_tetikler(monkeypatch):
    """finish_reason=MALFORMED_FUNCTION_CALL → ProviderEmptyResponseError (fallback geçişi)."""
    _install_fake_genai(monkeypatch, _resp("MALFORMED_FUNCTION_CALL", [_text_part("kismi")]))
    p = GeminiProvider(api_key="k")
    with pytest.raises(ProviderEmptyResponseError):
        p._raw_chat("sys", [{"role": "user", "content": "x"}], tools=[])


def test_safety_finish_reason_fallback(monkeypatch):
    _install_fake_genai(monkeypatch, _resp("SAFETY", None))
    p = GeminiProvider(api_key="k")
    with pytest.raises(ProviderEmptyResponseError):
        p._raw_chat("sys", [{"role": "user", "content": "x"}], tools=[])


def test_bos_candidates_fallback(monkeypatch):
    _install_fake_genai(monkeypatch, _resp(candidates_empty=True))
    p = GeminiProvider(api_key="k")
    with pytest.raises(ProviderEmptyResponseError):
        p._raw_chat("sys", [{"role": "user", "content": "x"}], tools=[])


def test_bos_text_ve_tool_fallback(monkeypatch):
    """finish=STOP ama hiç part yok → boş text + boş tool → fallback."""
    _install_fake_genai(monkeypatch, _resp("STOP", []))
    p = GeminiProvider(api_key="k")
    with pytest.raises(ProviderEmptyResponseError):
        p._raw_chat("sys", [{"role": "user", "content": "x"}], tools=[])


def test_kullanilan_genai_sembolleri_gercek_SDK_de_VAR():
    """Sahte modül her adı üretir; o hâlde GERÇEK yüzeyi ayrıca denetlemek ŞART.

    Aksi halde `genai_types.OlmayanSinif(...)` yazsak süit yeşil kalır ve hata yalnız
    canlıda, gerçek bir koç isteğinde ortaya çıkar (KURAL R3: sessiz yanlış en pahalısı).
    """
    import re
    from pathlib import Path

    genai_types = pytest.importorskip("google.genai.types")   # kurulu değilse ölçme
    kaynak = (Path(__file__).resolve().parents[1] / "app/coach.py").read_text(encoding="utf-8")
    semboller = set(re.findall(r"\bgenai_types\.(\w+)", kaynak)) | \
                set(re.findall(r"\bself\.types\.(\w+)", kaynak))
    assert semboller, "app/coach.py'de genai types kullanımı bulunamadı (kapı ölçmüyor)"
    eksik = sorted(a for a in semboller if not hasattr(genai_types, a))
    assert not eksik, f"google.genai.types içinde OLMAYAN semboller kullanılıyor: {eksik}"
