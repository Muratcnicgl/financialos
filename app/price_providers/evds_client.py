"""
M12 (ADR-031): TCMB EVDS fiyat sağlayıcı — döviz (USD/EUR/…) + altın kuru.

EVDS resmi TCMB kaynağıdır (KVKK-uyumlu yurt-içi). **API_KEY_TALEP:** EVDS_API_KEY
(evds.tcmb.gov.tr ücretsiz kayıt). Key yoksa None döner (scaffold).

Seri kodları (yaygın): USD alış=TP.DK.USD.A, EUR=TP.DK.EUR.A, gram altın=TP.MK.CUM.YTL.
`symbol` → EVDS seri koduna eşlenir (basit sözlük; genişletilebilir).
"""
from __future__ import annotations

import logging
import math
import os
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

# Basit sembol → EVDS seri kodu eşlemesi (genişletilebilir)
_SERIES = {
    "USDTRY": "TP.DK.USD.A",
    "EURTRY": "TP.DK.EUR.A",
    "GBPTRY": "TP.DK.GBP.A",
    "XAU": "TP.MK.CUM.YTL",      # gram altın (TL)
    "GOLD": "TP.MK.CUM.YTL",
}


def get_evds_price(symbol: str) -> Optional[Decimal]:
    """Döviz/altın son değeri (Decimal) veya None. EVDS_API_KEY gerekli (yoksa None)."""
    if not symbol:
        return None
    api_key = os.getenv("EVDS_API_KEY")
    if not api_key:
        logger.info("[evds] EVDS_API_KEY tanımsız — %s atlandı (API_KEY_TALEP)", symbol)
        return None
    series = _SERIES.get(symbol.upper())
    if not series:
        logger.warning("[evds] %s için seri kodu tanımsız", symbol)
        return None
    try:
        import requests
        url = "https://evds2.tcmb.gov.tr/service/evds/"
        params = {
            "series": series, "type": "json",
            "aggregationTypes": "last", "lastObservations": 1,
        }
        r = requests.get(url, params=params, headers={"key": api_key}, timeout=15)
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return None
        raw = next((v for k, v in items[0].items() if k != "Tarih" and v), None)
        if raw is None:
            return None
        val = float(raw)
        if not math.isfinite(val) or val <= 0:
            return None
        return Decimal(str(val)).quantize(Decimal("0.0001"))
    except Exception as e:  # noqa: BLE001
        logger.warning("[evds] %s çekim hatası: %s", symbol, e)
        return None
