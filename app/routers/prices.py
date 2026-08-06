"""
M19-v3 (ADR-029 revize) — Fiyat sorgulama HTTP endpoint'leri (TCMB EVDS v3 döviz + altın).

R3 (14 Tem 2026): EVDS v3 geçişi (M19 regression fix) — evds2→evds3 canlı doğrulandı
(USD alış 46.91 / satış 47.00, 14 Tem). Döviz kusursuz. Altın `TP.MK.F.BILESIK.TUM`
TCMB **bileşik-fon endeksi** döner (gram-altın-TL değil; charter/PDF örnek serisi).

BUG #246 fix (D32): uçlar artık PUBLIC DEĞİL. Piyasa verisi kullanıcı verisi taşımaz ama her
istek TCMB EVDS'ye 30 sn timeout'lu SENKRON bir dış çağrı tetikliyordu; kimliksiz bir istemci
bunu tekrarlayarak Starlette threadpool'unu doldurabilir (gerçek kullanıcı cockpit'e erişemez)
ve operatörün EVDS kotasını yakabilirdi. Kimlik + hız sınırı: iki satırlık kapatma, karşılığı
tüm uygulamanın erişilebilirliği. Scheduler fx/gold hesaplarını `fetch_for_account` dispatch'i
ile çeker (M12) — o yol HTTP katmanından geçmez, etkilenmez.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.dependencies import get_current_user
from app.models import User
from app.rate_limit import rate_limit

from app.price_providers.evds_client import fetch_currency_rate, fetch_gold_price

router = APIRouter(prefix="/api/prices", tags=["prices"])


def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "date formatı YYYY-MM-DD olmalı.")


@router.get("/currency/{currency_code}")
def currency_price(
    currency_code: str,
    request: Request,
    date_str: Optional[str] = Query(None, alias="date"),
    user: User = Depends(get_current_user),   # BUG #246 (D32): kimliksiz dış çağrı yok
) -> dict:
    """Döviz kuru alış+satış (TCMB EVDS v3). Örn: /api/prices/currency/USD."""
    rate_limit(request, "prices")
    target = _parse_date(date_str)
    rate = fetch_currency_rate(currency_code, target)
    if not rate or (rate.get("buy") is None and rate.get("sell") is None):
        raise HTTPException(
            status_code=502,
            detail=(f"{currency_code.upper()} kuru alınamadı (EVDS erişilemedi veya seri yok). "
                    f"EVDS_API_KEY + endpoint yapılandırmasını kontrol edin."),
        )
    return {
        "currency": currency_code.upper().replace("TRY", "") or currency_code.upper(),
        "rate_buy": str(rate["buy"]) if rate.get("buy") is not None else None,
        "rate_sell": str(rate["sell"]) if rate.get("sell") is not None else None,
        "date": rate["date"],
        "source": rate["source"],
    }


@router.get("/gold/{gold_type}")
def gold_price(
    gold_type: str,
    request: Request,
    date_str: Optional[str] = Query(None, alias="date"),
    user: User = Depends(get_current_user),   # BUG #246 (D32)
) -> dict:
    """Altın fiyatı (TCMB EVDS v3 bileşik-fon endeksi). Örn: /api/prices/gold/bilesik.

    NOT: TP.MK.F.BILESIK.TUM TCMB bileşik-fon endeksidir (gram-altın-TL değil).
    """
    rate_limit(request, "prices")
    target = _parse_date(date_str)
    g = fetch_gold_price(gold_type, target)
    if not g:
        raise HTTPException(502, "Altın fiyatı alınamadı (EVDS erişilemedi). Yapılandırmayı kontrol edin.")
    return {"type": gold_type, "price": str(g["price"]), "date": g["date"], "source": g["source"]}
