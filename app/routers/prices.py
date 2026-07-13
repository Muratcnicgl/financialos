"""
M19 (ADR-031) — Fiyat sorgulama HTTP endpoint'leri (TCMB EVDS döviz + altın).

R3 (14 Tem 2026): EVDS `evds2.tcmb.gov.tr/service/evds/` şu an SPA HTML döndürüyor
(API endpoint taşınmış/erişilemez — M12 yfinance durumunun tekrarı). Kod doğru-yapılı;
canlı fiyat gelene kadar `get_evds_price` None döner → endpoint 502 (net mesaj).
Doğru EVDS endpoint/key doğrulaması Murat'ın ortamında.

Endpoint'ler PUBLIC (piyasa verisi, auth yok). Scheduler zaten fx/gold hesaplarını
`fetch_for_account` dispatch'i ile çeker (M12); bunlar on-demand sorgu içindir.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.price_providers.evds_client import get_evds_price

router = APIRouter(prefix="/api/prices", tags=["prices"])

# Altın türü → EVDS sembolü (evds_client._SERIES ile uyumlu)
_GOLD_SYMBOLS = {
    "gram": "XAU", "gram_altin": "XAU", "gramaltin": "XAU",
    "xau": "XAU", "gold": "GOLD", "altin": "XAU",
}


@router.get("/currency/{currency_code}")
def currency_price(currency_code: str) -> dict:
    """Döviz kuru (TCMB EVDS). Örn: /api/prices/currency/USD → USD/TRY."""
    code = currency_code.upper().strip()
    symbol = code if code.endswith("TRY") else f"{code}TRY"
    price = get_evds_price(symbol)
    if price is None:
        raise HTTPException(
            status_code=502,
            detail=(f"{code} kuru alınamadı (EVDS erişilemedi veya seri tanımsız). "
                    f"EVDS_API_KEY + endpoint yapılandırmasını kontrol edin."),
        )
    return {"currency": code, "rate": str(price), "source": "TCMB_EVDS"}


@router.get("/gold/{gold_type}")
def gold_price(gold_type: str) -> dict:
    """Altın fiyatı (TCMB EVDS). Örn: /api/prices/gold/gram."""
    symbol = _GOLD_SYMBOLS.get(gold_type.lower().strip(), "XAU")
    price = get_evds_price(symbol)
    if price is None:
        raise HTTPException(
            status_code=502,
            detail="Altın fiyatı alınamadı (EVDS erişilemedi). EVDS yapılandırmasını kontrol edin.",
        )
    return {"type": gold_type, "price": str(price), "source": "TCMB_EVDS"}
