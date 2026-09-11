"""
BE-002 / BUG #399 KAPISI — OPENAI-UYUMLU SAĞLAYICILARIN TEK `_raw_chat` GÖVDESİ VAR.

Ölçülen (11 Eyl 2026): `_OpenAICompatMixin` 13 Tem'de yazılmıştı ama yalnız Together ve
DeepInfra kullanıyordu. Cerebras ve OpenRouter'ın `_raw_chat`'i mixin'le bayt bayt aynıydı;
Groq'unki tek farkla (boş araç listesini de gönderiyordu) kopyaydı. Bir hata dört yerde
düzeltiliyordu — madde 60+ gündür "kısmen". 148 satır silindi, 42 eklendi.

Kilitlenen: `chat.completions` arayüzü kullanan her sağlayıcı sınıfının `_raw_chat`'i
mixin'in fonksiyonunun TA KENDİSİ (yeniden tanımlanmış kopya kırmızı) ve mixin'in gövdesi
araç/kullanım sözleşmesini korur (sahte istemciyle).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app import coach

OPENAI_UYUMLU = (coach.GroqProvider, coach.CerebrasProvider, coach.OpenRouterProvider,
                 coach.TogetherProvider, coach.DeepInfraProvider)


@pytest.mark.parametrize("sinif", OPENAI_UYUMLU, ids=lambda c: c.__name__)
def test_raw_chat_mixin_in_kendisi(sinif):
    # LLMProvider.__init_subclass__ her alt sınıfa kota sayan bir sarmal takar (BUG #234);
    # sarmalın altındaki gerçek gövde `__wrapped__`tır — kimlik orada ölçülür.
    ham = getattr(sinif._raw_chat, "__wrapped__", sinif._raw_chat)
    assert ham is coach._OpenAICompatMixin._raw_chat, f"{sinif.__name__}: kopya _raw_chat"
    assert sinif.chat is coach._OpenAICompatMixin.chat


class _SahteIstemci:
    def __init__(self, cevap):
        self.cevap = cevap
        self.son_kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.son_kwargs = kwargs
        return self.cevap


def _cevap(icerik="ok", tool_calls=None, usage=(10, 5)):
    msg = SimpleNamespace(content=icerik, tool_calls=tool_calls)
    u = SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1]) if usage else None
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=u)


def _saglayici(sinif, cevap):
    p = object.__new__(sinif)
    p.client = _SahteIstemci(cevap)
    p.model = "m"
    return p


@pytest.mark.parametrize("sinif", OPENAI_UYUMLU, ids=lambda c: c.__name__)
def test_bos_arac_listesi_GONDERILMEZ_ve_kimlik_dogru(sinif):
    """Groq eskiden `tools=[]` gönderiyordu; ortak gövde araç yoksa alanı hiç koymaz."""
    p = _saglayici(sinif, _cevap())
    r = p._raw_chat("sys", [{"role": "user", "content": "x"}], tools=[])
    assert "tools" not in p.client.son_kwargs and "tool_choice" not in p.client.son_kwargs
    assert p.client.son_kwargs["messages"][0] == {"role": "system", "content": "sys"}
    assert r.provider_used == sinif.NAME.lower() and r.model_name == "m"
    assert r.usage == {"input_tokens": 10, "output_tokens": 5}


def test_arac_cagrisi_ve_bozuk_arguman():
    tc_ok = SimpleNamespace(function=SimpleNamespace(name="propose_action", arguments=json.dumps({"amount": 250})))
    tc_bozuk = SimpleNamespace(function=SimpleNamespace(name="propose_action", arguments="{bozuk"))
    p = _saglayici(coach.GroqProvider, _cevap("", [tc_ok, tc_bozuk]))
    r = p._raw_chat("sys", [{"role": "user", "content": "x"}],
                    tools=[{"name": "propose_action", "description": "d", "parameters": {}}])
    assert p.client.son_kwargs["tools"][0]["function"]["name"] == "propose_action"
    assert p.client.son_kwargs["tool_choice"] == "auto"
    assert r.tool_calls == [{"name": "propose_action", "input": {"amount": 250}},
                            {"name": "propose_action", "input": {}}]
