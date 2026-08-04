"""
M12 (ADR-031): yfinance fiyat sağlayıcı — global hisse + (deneme) BIST (`.IS` suffix).

R3 UYARISI (13 Tem 2026): Bu ortamda Yahoo Finance erişilemez (THYAO.IS ve AAPL
"no price data" döndü — network/rate-limit blok). Kod doğru; canlı doğrulama kullanıcının
ortamında gerekli. Erişilemezse None döner (fund_tracker deseni — sessiz fallback).
Sonlu-değer güvenliği (SEC-032): NaN/inf reddedilir.
"""
from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


def get_yfinance_price(symbol: str) -> Optional[Decimal]:
    """Sembolün son kapanış fiyatı (Decimal) veya None. BIST için '<KOD>.IS' ver."""
    if not symbol:
        return None
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period="5d")
        if hist is None or len(hist) == 0:
            logger.warning("[yfinance] %s: fiyat verisi yok (erişilemez/delisted)", symbol)
            return None
        close = float(hist["Close"].iloc[-1])
        if not math.isfinite(close) or close <= 0:
            return None
        return Decimal(str(close)).quantize(Decimal("0.0001"))
    except Exception as e:  # noqa: BLE001 — dış kaynak, her hata sessiz fallback
        logger.warning("[yfinance] %s çekim hatası: %s", symbol, e)
        return None
