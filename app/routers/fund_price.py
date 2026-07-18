"""
Fund price endpoint'leri (3):
- POST /api/fund-price/update         - Manuel fiyat guncelleme (lot * price -> balance)
- GET  /api/fund-price/freshness      - Tum fonlarin yas durumu (Cockpit rozetleri)
- GET  /api/fund-price/tefas-link/{fund_code}  - TEFAS sayfa URL'i

NOT (2 Mayis 2026 fix #001): fund_tracker.py imzalari dogrulandi:
- get_freshness_summary(db, user_id)
- update_fund_price_manual(db, account_id, new_price)
- get_tefas_url(fund_code)
\u00d6nceki versiyonda try/except imza tahmini vardi, kaldirildi.

NOT: Otomatik TEFAS cekme su an YOK (TEFAS API kapali, F5 Bot Defense). Cozum:
B Plani 'Manuel + Akilli UI' \u2014 kullanici TEFAS'tan baktigi fiyati buraya girer,
last_price_update otomatik damgalanir, 24+ saat eski ise rozet cikar.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from typing import Optional
from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id, scope_filter  # M70 workspace scoping
from app.models import User, Account, AccountType
from app.schema_types import FinansTutar  # SEC-032: sonlu/pozitif fiyat (inf → lot*inf=inf bakiye)
from app.fund_tracker import (
    get_tefas_url,
    update_fund_price_manual,
    get_freshness_summary,
)

router = APIRouter(prefix="/api/fund-price", tags=["fund_price"])


# ============================================================
# SCHEMAS
# ============================================================

class FundPriceUpdate(BaseModel):
    account_id: int = Field(..., description="Yatirim hesabinin id'si")
    new_price: FinansTutar  # SEC-032: gt=0 + sonlu + üst sınır (inf/1e308 → inf bakiye önlenir)


class FundPriceUpdateResponse(BaseModel):
    ok: bool
    account_id: int
    fund_code: Optional[str]
    old_price: Optional[float]
    new_price: float
    new_value: float
    lot_count: float
    timestamp: str
    message: str


class TefasLinkResponse(BaseModel):
    fund_code: str
    url: str


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.post("/update", response_model=FundPriceUpdateResponse)
def update_price(
    payload: FundPriceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M70
) -> FundPriceUpdateResponse:
    """
    Yatirim hesabinin fiyatini manuel guncelle.

    Yan etkiler:
    - last_price_update otomatik su an'a set edilir (timestamp)
    - balance = lot_count * new_price seklinde otomatik hesaplanir

    Onerilen kullanim: Frontend her sabah TEFAS'a baktiginda buraya 1 sayi yazar,
    Cockpit kendiliginden taze fiyatla gosterir.
    """
    # Once kullanicinin sahip oldugu hesabi dogrula (security)
    acc = db.query(Account).filter(
        Account.id == payload.account_id,
        scope_filter(Account, user.id, ws_id),  # M70 workspace scoping
    ).first()
    if not acc:
        raise HTTPException(404, f"Hesap bulunamadi (id={payload.account_id})")
    if acc.account_type != AccountType.investment:
        raise HTTPException(
            400,
            f"Sadece yatirim hesabi guncellenir. Bu hesap: {acc.account_type.value}",
        )

    # Imza: update_fund_price_manual(db, account_id, new_price, user_id)
    result = update_fund_price_manual(
        db=db,
        account_id=payload.account_id,
        new_price=payload.new_price,
        user_id=user.id,   # BUG #115: sahiplik kapsamı
    )

    if not result.get("success"):
        raise HTTPException(400, result.get("message", "Fiyat guncellenemedi"))

    return FundPriceUpdateResponse(
        ok=True,
        account_id=result["account_id"],
        fund_code=result.get("fund_code"),
        old_price=result.get("old_price"),
        new_price=result["new_price"],
        new_value=result["new_value"],
        lot_count=result["lot_count"],
        timestamp=result["timestamp"],
        message=result.get("message", ""),
    )


@router.get("/freshness")
def get_freshness(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Tum yatirim hesaplari icin fiyat yasi ozeti.
    Cockpit'in 'TLY fiyati 31 saat eski' rozetinin kaynagi.

    Donus alanlari:
    - total_investments: int
    - stale_count: int (24+ saat eski olan)
    - never_set_count: int (hic fiyat girilmemis olan)
    - items: List[{account_id, name, fund_code, is_emanet, current_price,
                   last_update, age_text, is_stale, tefas_url}]
    """
    return get_freshness_summary(db, user.id)


@router.get("/tefas-link/{fund_code}", response_model=TefasLinkResponse)
def tefas_link(fund_code: str) -> TefasLinkResponse:
    """
    TEFAS fon sayfasi URL'i. Frontend butonuna 'TEFAS'ta Ac' link verir.
    Kullanici tek tikla fonu acar, fiyati gorur, /api/fund-price/update'e yazar.
    """
    return TefasLinkResponse(
        fund_code=fund_code.upper(),
        url=get_tefas_url(fund_code),
    )

