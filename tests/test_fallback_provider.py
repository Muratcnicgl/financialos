"""
FallbackProvider — çoklu-sağlayıcı dayanıklılık (founding Sovereign + fallback çekirdeği).
Birincil kota/boş/kod-hatası verirse SONRAKİNE geçilir; hepsi düşerse son hata raise.
"""
from __future__ import annotations

import pytest

from app.coach import FallbackProvider, LLMResponse, ProviderEmptyResponseError


class FakeProvider:
    def __init__(self, name, result=None, exc=None):
        self.NAME = name
        self.model = f"{name}-model"
        self._result = result
        self._exc = exc

    def chat(self, system_prompt, messages, tools):
        if self._exc:
            raise self._exc
        return self._result


def _ok(name):
    return FakeProvider(name, result=LLMResponse(text="ok", tool_calls=[]))


def test_ilk_provider_basarili_kullanilir():
    fb = FallbackProvider([_ok("A"), _ok("B")])
    r = fb.chat("s", [], [])
    assert r.text == "ok"
    assert fb.last_used_provider == "A"
    assert fb.fallback_count == 0


def test_kota_hatasinda_sonrakine_gecer():
    fb = FallbackProvider([FakeProvider("A", exc=Exception("429 RESOURCE_EXHAUSTED quota")), _ok("B")])
    fb.chat("s", [], [])
    assert fb.last_used_provider == "B"
    assert fb.fallback_count == 1


def test_bos_cevapta_sonrakine_gecer():
    fb = FallbackProvider([FakeProvider("A", exc=ProviderEmptyResponseError("bos/bozuk", "MALFORMED_FUNCTION_CALL")), _ok("B")])
    fb.chat("s", [], [])
    assert fb.last_used_provider == "B"


def test_generic_kod_hatasinda_da_gecer(caplog):
    """BUG #093: kota-dışı beklenmedik hata da sonrakine geçirir (ve ERROR loglanır)."""
    fb = FallbackProvider([FakeProvider("A", exc=ValueError("kod bug")), _ok("B")])
    fb.chat("s", [], [])
    assert fb.last_used_provider == "B"


def test_hepsi_duserse_son_hata_raise():
    fb = FallbackProvider([
        FakeProvider("A", exc=Exception("429 quota")),
        FakeProvider("B", exc=Exception("429 quota")),
    ])
    with pytest.raises(Exception):
        fb.chat("s", [], [])


def test_bos_provider_listesi_reddedilir():
    with pytest.raises(ValueError):
        FallbackProvider([])


def test_provider_used_backfill():
    fb = FallbackProvider([_ok("Groq")])
    r = fb.chat("s", [], [])
    assert r.provider_used == "groq"      # NAME.lower() ile doldurulur


# ---- RESIL-008: circuit breaker (request too large / context limit) --------

class CountingProvider:
    """chat çağrı sayısını sayar — atlanan sağlayıcının TEKRAR ÇAĞRILMADIĞINI doğrular."""
    def __init__(self, name, result=None, exc=None):
        self.NAME = name
        self.model = f"{name}-model"
        self._result = result
        self._exc = exc
        self.calls = 0

    def chat(self, system_prompt, messages, tools):
        self.calls += 1
        if self._exc:
            raise self._exc
        return self._result


def test_request_too_large_provider_kalici_atlanir():
    """RESIL-008: 'request too large' veren sağlayıcı ikinci çağrıda HİÇ denenmemeli."""
    groq = CountingProvider("Groq", exc=Exception(
        "Error code: 413 - Request too large for model, please reduce your message size"))
    gemini = CountingProvider("Gemini", result=LLMResponse(text="ok", tool_calls=[]))
    fb = FallbackProvider([groq, gemini])

    fb.chat("s", [], [])                    # 1. çağrı: Groq 413 → Gemini
    assert fb.last_used_provider == "Gemini"
    assert groq.calls == 1 and gemini.calls == 1
    assert "Groq" in fb._oversized_providers

    fb.chat("s", [], [])                    # 2. çağrı: Groq ATLANIR (tekrar çağrılmaz)
    assert fb.last_used_provider == "Gemini"
    assert groq.calls == 1                   # hâlâ 1 — beyhude round-trip yok
    assert gemini.calls == 2


def test_413_status_code_kalici_sayilir():
    class E413(Exception):
        status_code = 413
    groq = CountingProvider("Groq", exc=E413("too big"))
    gemini = CountingProvider("Gemini", result=LLMResponse(text="ok", tool_calls=[]))
    fb = FallbackProvider([groq, gemini])
    fb.chat("s", [], [])
    assert "Groq" in fb._oversized_providers


def test_gecici_kota_kalici_atlamaz():
    """429 (geçici kota) request-too-large DEĞİL → kalıcı atlama listesine GİRMEZ."""
    groq = CountingProvider("Groq", exc=Exception("429 RESOURCE_EXHAUSTED quota"))
    gemini = CountingProvider("Gemini", result=LLMResponse(text="ok", tool_calls=[]))
    fb = FallbackProvider([groq, gemini])
    fb.chat("s", [], [])
    assert "Groq" not in fb._oversized_providers    # geçici — bir sonraki çağrıda yine denenir
    fb.chat("s", [], [])
    assert groq.calls == 2                            # geçici kota her çağrıda yeniden denenir


def test_hepsi_oversized_ise_yine_tam_listeye_doner():
    """Güvenlik: tüm sağlayıcılar oversized işaretliyse bile çağrı çökmez, tam listeyi dener."""
    p = CountingProvider("Only", exc=Exception("request too large"))
    fb = FallbackProvider([p])
    with pytest.raises(Exception):
        fb.chat("s", [], [])
    assert "Only" in fb._oversized_providers
    # ikinci çağrı: tek sağlayıcı oversized ama candidates boş kalmasın → yine denenir (raise)
    with pytest.raises(Exception):
        fb.chat("s", [], [])
    assert p.calls == 2
