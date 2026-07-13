"""
M13 (ADR-034 revize) — yeni ücretsiz sağlayıcılar (Together, DeepInfra) + fallback zinciri.

Canlı çağrı API key gerektirir (API_KEY_TALEP) → build mantığı + zincir sırası test edilir.
"""
from __future__ import annotations

import app.coach as coach


def test_together_build_keysiz_none(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    assert coach._build_together() is None


def test_together_build_keyli(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "dummy")
    p = coach._build_together()
    assert p is not None and p.NAME == "Together"
    assert "Llama" in p.model


def test_deepinfra_build_keysiz_none(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    assert coach._build_deepinfra() is None


def test_deepinfra_build_keyli(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "dummy")
    p = coach._build_deepinfra()
    assert p is not None and p.NAME == "DeepInfra"


def test_openai_compat_mixin_ortak_govde():
    # Together + DeepInfra + (mevcut desen) aynı _raw_chat gövdesini paylaşır
    assert hasattr(coach.TogetherProvider, "_raw_chat")
    assert hasattr(coach.DeepInfraProvider, "chat")
    assert coach.TogetherProvider.BASE_URL != coach.DeepInfraProvider.BASE_URL


def test_fallback_zinciri_yeni_saglayicilari_icerir(monkeypatch):
    # Tüm key'ler set → zincir 7 sağlayıcıyı içermeli (sıra ADR-034 revize)
    for k in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "CEREBRAS_API_KEY",
              "TOGETHER_API_KEY", "DEEPINFRA_API_KEY", "GROQ_API_KEY"):
        monkeypatch.setenv(k, "dummy")
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    monkeypatch.setenv("OLLAMA_ENABLED", "0")
    prov = coach.build_provider()
    # FallbackProvider veya tek provider; NAME'leri topla
    names = [p.NAME for p in getattr(prov, "providers", [prov])]
    assert "Together" in names and "DeepInfra" in names
    # Sıra: Gemini ilk
    assert names[0] == "Gemini"
