"""
M19-v3 (ADR-029 revize) — TCMB EVDS v3 fiyat sağlayıcı: döviz + altın.

R3 (14 Tem 2026): EVDS **v3'e taşındı** — eski `evds2.tcmb.gov.tr/service/evds/` 405/SPA
döndürüyordu (M19 regression). Yeni v3 canlı doğrulandı (USD alış 46.7854 / satış 46.8697).

v3 gerçekleri (EVDS Web Servis + Python Kılavuzu, Murat 14 Tem):
- Base: https://evds3.tcmb.gov.tr/igmevdsms-dis
- Format: {base}/series=<KODLAR>&startDate=<gg-aa-yyyy>&endDate=<gg-aa-yyyy>&type=json
  (series PATH'e gömülü, query-param DEĞİL; çoklu seri tire ile: A-B-C)
- Auth: HTTP header {"key": EVDS_API_KEY} (query-param DEĞİL; iletmeyene 403)
- Response: items listesi; seri kodundaki noktalar '_' olur (TP.DK.USD.A → TP_DK_USD_A);
  değerler string ("46.78540000") veya null (hafta sonu/tatil).
- Max 1000 gözlem/istek. Seri kodları KORUNDU (v2→v3).

**API_KEY_TALEP:** EVDS_API_KEY (evds3.tcmb.gov.tr Profilim > API Key Kopyala).
"""
from __future__ import annotations

import logging
import math
import os
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"
SOURCE = "TCMB_EVDS_v3"

# Altın türü → EVDS bileşik seri kodu (Python Kılavuzu Örnek 2)
_GOLD_SERIES = {
    "bilesik": "TP.MK.F.BILESIK.TUM",
    "gram": "TP.MK.F.BILESIK.TUM",
    "gram_altin": "TP.MK.F.BILESIK.TUM",
    "xau": "TP.MK.F.BILESIK.TUM",
    "gold": "TP.MK.F.BILESIK.TUM",
    "altin": "TP.MK.F.BILESIK.TUM",
}

# Basit TTL cache: (series_key, tarih) -> (value, ts). Aynı gün tekrar çekimi önler.
_CACHE: dict[str, tuple[dict, float]] = {}
_TTL = 4 * 3600  # 4 saat


def _fmt(d: date) -> str:
    return d.strftime("%d-%m-%Y")  # EVDS: gg-aa-yyyy


def _to_decimal(raw) -> Optional[Decimal]:
    if raw is None:
        return None
    try:
        v = Decimal(str(raw))
    except Exception:
        return None
    if not v.is_finite() or v <= 0:
        return None
    return v.quantize(Decimal("0.0001"))


def fetch_series(series_codes: list[str], start: date, end: date) -> Optional[dict]:
    """v3 seri çekimi. {seri_kodu(underscore'lu): [(tarih, Decimal)...]} veya None.

    Hata (403 key/405 endpoint/timeout/JSON) → log + None (akış bozulmaz).
    """
    api_key = os.getenv("EVDS_API_KEY", "").strip()
    if not api_key:
        logger.info("[evds] EVDS_API_KEY tanımsız — atlandı (API_KEY_TALEP)")
        return None
    if not series_codes:
        return None
    joined = "-".join(series_codes)
    url = f"{BASE_URL}/series={joined}&startDate={_fmt(start)}&endDate={_fmt(end)}&type=json"
    try:
        r = requests.get(url, headers={"key": api_key}, timeout=30)
        if r.status_code != 200:
            logger.warning("[evds] HTTP %s (%s)", r.status_code, joined)
            return None
        items = r.json().get("items", [])
    except Exception as e:  # noqa: BLE001
        logger.warning("[evds] çekim hatası (%s): %s", joined, e)
        return None

    out: dict[str, list] = {}
    for code in series_codes:
        key = code.replace(".", "_")
        series_points = []
        for it in items:
            val = _to_decimal(it.get(key))
            if val is not None:
                series_points.append((it.get("Tarih"), val))
        out[key] = series_points
    return out


def _last(points: list) -> Optional[tuple]:
    """Serideki en güncel (tarih, Decimal) — hafta sonu null'ları atlar."""
    return points[-1] if points else None


def _window(target_date: Optional[date]) -> tuple[date, date]:
    end = target_date or date.today()
    return end - timedelta(days=7), end  # hafta sonu/tatil için 7 gün geriye bak


def fetch_currency_rate(code: str, target_date: Optional[date] = None) -> Optional[dict]:
    """Döviz alış+satış (TP.DK.{code}.A/.S). {"buy","sell","date"} veya None."""
    code = code.upper().strip()
    if code.endswith("TRY"):
        code = code[:-3]  # USDTRY → USD
    start, end = _window(target_date)
    cache_key = f"fx:{code}:{end.isoformat()}"
    hit = _CACHE.get(cache_key)
    if hit and (time.time() - hit[1]) < _TTL:
        return hit[0]

    res = fetch_series([f"TP.DK.{code}.A", f"TP.DK.{code}.S"], start, end)
    if not res:
        return None
    buy = _last(res.get(f"TP_DK_{code}_A", []))
    sell = _last(res.get(f"TP_DK_{code}_S", []))
    if not buy and not sell:
        return None
    out = {
        "buy": buy[1] if buy else None,
        "sell": sell[1] if sell else None,
        "date": (buy or sell)[0],
        "source": SOURCE,
    }
    _CACHE[cache_key] = (out, time.time())
    return out


def fetch_gold_price(gold_type: str = "bilesik", target_date: Optional[date] = None) -> Optional[dict]:
    """Altın fiyatı (TP.MK.F.BILESIK.TUM). {"price","date"} veya None."""
    series = _GOLD_SERIES.get(gold_type.lower().strip(), "TP.MK.F.BILESIK.TUM")
    start, end = _window(target_date)
    cache_key = f"gold:{series}:{end.isoformat()}"
    hit = _CACHE.get(cache_key)
    if hit and (time.time() - hit[1]) < _TTL:
        return hit[0]
    res = fetch_series([series], start, end)
    if not res:
        return None
    point = _last(res.get(series.replace(".", "_"), []))
    if not point:
        return None
    out = {"price": point[1], "date": point[0], "source": SOURCE}
    _CACHE[cache_key] = (out, time.time())
    return out


def get_evds_price(symbol: str) -> Optional[Decimal]:
    """Geriye-uyum: tek Decimal döner (döviz→alış, altın→fiyat).

    price_providers/router.py fetch_for_account dispatch'i bunu kullanır (fx/gold hesap).
    """
    if not symbol:
        return None
    s = symbol.upper().strip()
    if s in _GOLD_SERIES or s.startswith("XAU") or s in ("GOLD", "ALTIN"):
        g = fetch_gold_price(s)
        return g["price"] if g else None
    fx = fetch_currency_rate(s)
    return fx["buy"] if fx and fx.get("buy") else None
