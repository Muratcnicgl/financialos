"""
FEAT-032: Koç için CANLI döviz kuru (USD/TRY, EUR/TRY) — keyless.

Koçun "dolar kuru kaç?" sorusunda UYDURMAMASI için gerçek veri sağlar (ADR-001 grounding).
Kaynak: open.er-api.com (ücretsiz, API-key GEREKMEZ — EVDS'in aksine). Kapsam SCOPED: yalnız
döviz (açık web araması DEĞİL → koç "finansal danışman" kalır, egemenlik korunur).

Graceful degradation (proje deseni): ağ/servis/parse hatası → None. Koç None'da "canlı veri
alamadım" der, UYDURMAZ. 30 dk in-process TTL cache (döviz gün içi değişir; kaynağı hammer'lamaz).
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

_URL = "https://open.er-api.com/v6/latest/USD"
_TIMEOUT = 8
_TTL = 30 * 60  # 30 dk
_CACHE: Dict[str, tuple] = {}  # {"fx": (data, epoch_ts)}


def get_live_fx() -> Optional[Dict]:
    """Canlı döviz döner ya da None (uydurma değil).

    Dönüş: {"usd_try": Decimal, "eur_try": Decimal, "guncelleme": str, "kaynak": str}
    open.er-api base=USD verir: rates.TRY = 1 USD kaç TL; rates.EUR = 1 USD kaç EUR
    → EUR/TRY = rates.TRY / rates.EUR.
    """
    now = time.time()
    cached = _CACHE.get("fx")
    if cached and now - cached[1] < _TTL:
        return cached[0]
    try:
        resp = requests.get(_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("result") != "success":
            logger.warning("[fx_live] beklenmeyen result=%s", payload.get("result"))
            return None
        rates = payload.get("rates") or {}
        usd_try = rates.get("TRY")
        usd_eur = rates.get("EUR")
        if not usd_try or not usd_eur:
            logger.warning("[fx_live] TRY/EUR oranı eksik")
            return None
        data = {
            "usd_try": round(Decimal(str(usd_try)), 4),
            "eur_try": round(Decimal(str(usd_try)) / Decimal(str(usd_eur)), 4),
            "guncelleme": payload.get("time_last_update_utc", "?"),
            "kaynak": "open.er-api.com",
        }
        _CACHE["fx"] = (data, now)
        return data
    except Exception as e:  # noqa: BLE001 — dış API; grounding gereği hata→None (uydurma yok)
        logger.warning("[fx_live] canlı döviz alınamadı: %s", e)
        return None
