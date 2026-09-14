"""
LLM-030 (BUG #501): çıktı token tavanı tek kaynak ve ayarlanabilir; kesilme sessiz değil.

Ölçüm (14 Eyl 2026): `max_tokens=4096` üç sağlayıcı dalında sabit yazılıydı; yanıt sınırda
kesildiğinde (Anthropic `stop_reason=max_tokens`, OpenAI `finish_reason=length`, Gemini
`MAX_TOKENS`) bunu izde/log'da söyleyen yoktu — koç cümle ortasında susuyor, kullanıcı
"bozuk" sanıyordu. Kilitlenen:
  1. `llm_max_tokens()` env'den okur, 256–32000 klempler, bozuk değerde 4096,
  2. üç sağlayıcı dalı da sabit 4096 yerine bu fonksiyonu çağırır (kaynak),
  3. `kesildi_mi` üç sağlayıcının bitiş adlarını tanır, diğerlerini tanımaz,
  4. chat akışı kesilmede iz gözlemine `[KESILDI…]` yazar ve log'lar (kaynak).
"""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

from app.coach import LLMResponse, kesildi_mi, llm_max_tokens

KOK = Path(__file__).resolve().parent.parent


def test_tavan_env_ve_klemp(monkeypatch):
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    assert llm_max_tokens() == 4096
    monkeypatch.setenv("LLM_MAX_TOKENS", "8000"); assert llm_max_tokens() == 8000
    monkeypatch.setenv("LLM_MAX_TOKENS", "5"); assert llm_max_tokens() == 256
    monkeypatch.setenv("LLM_MAX_TOKENS", "999999"); assert llm_max_tokens() == 32000
    monkeypatch.setenv("LLM_MAX_TOKENS", "bozuk"); assert llm_max_tokens() == 4096


def test_sabit_4096_kalmadi_uc_dal_tek_kaynaktan():
    src = (KOK / "app" / "coach.py").read_text(encoding="utf-8")
    assert not re.search(r"max_tokens\s*[=:]\s*4096", src), "sabit 4096 hâlâ var"
    assert not re.search(r"max_output_tokens=4096", src)
    assert src.count("llm_max_tokens()") >= 3, "üç sağlayıcı dalı da tek kaynağı çağırmalı"


def test_kesildi_mi_uc_saglayici():
    class G(Enum):
        MAX_TOKENS = 2
        STOP = 1
    assert kesildi_mi("max_tokens") and kesildi_mi("length") and kesildi_mi(G.MAX_TOKENS)
    assert not kesildi_mi("end_turn") and not kesildi_mi("stop") and not kesildi_mi(G.STOP) and not kesildi_mi(None)
    assert LLMResponse("x", []).kesildi is False


def test_chat_akisi_kesilmeyi_ize_yazar():
    src = (KOK / "app" / "coach.py").read_text(encoding="utf-8")
    assert '"[KESILDI: cikti token sinirina carpti] "' in src
    assert 'getattr(llm_response, "kesildi", False)' in src
    for dal in ('kesildi_mi(getattr(response, "stop_reason", None))', "kesildi_mi(finish_reason_str)",
                'kesildi_mi(getattr(response.choices[0], "finish_reason", None))'):
        assert dal in src, f"sağlayıcı dalı bayrağı üretmiyor: {dal}"
