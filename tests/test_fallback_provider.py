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
