"""
GET /api/subscriptions — tespit edilen abonelikler + toplam aylık/yıllık yük (FEAT-006).

Salt okuma denetim endpoint'i (Rocket Money "subscriptions" sekmesi ilhamı). İşlem
geçmişindeki tekrarlayan ödemeleri rules_engine.detect_subscriptions ile bulur; LLM/DB
yazımı yok. Bulunanlar ileride propose_action ile RecurringExpense'e dönüştürülebilir.
"""
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.rules_engine import detect_subscriptions
from app.dependencies import get_db, get_current_user
from app.models import User

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


class SubscriptionOut(BaseModel):
    isim: str
    anahtar: str
    period: str            # "monthly" | "annual"
    guncel_tutar: float
    aylik_maliyet: float
    tekrar: int
    son_tarih: str
    fiyat_degisti: bool    # FEAT-007 sinyali: tutar geçmişte değişmiş


class SubscriptionsResponse(BaseModel):
    abonelikler: List[SubscriptionOut]
    aylik_toplam: float
    yillik_toplam: float
    adet: int


@router.get("", response_model=SubscriptionsResponse)
def list_subscriptions(
    lookback_days: int = Query(180, ge=30, le=730, description="Kaç günlük geçmiş taransın"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionsResponse:
    """İşlem geçmişinden tekrarlayan abonelikleri tespit eder (salt okuma)."""
    return detect_subscriptions(user.id, date.today(), db, lookback_days=lookback_days)
