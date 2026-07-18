"""
GET /api/subscriptions — tespit edilen abonelikler + toplam aylık/yıllık yük (FEAT-006).

Salt okuma denetim endpoint'i (Rocket Money "subscriptions" sekmesi ilhamı). İşlem
geçmişindeki tekrarlayan ödemeleri rules_engine.detect_subscriptions ile bulur; LLM/DB
yazımı yok. Bulunanlar ileride propose_action ile RecurringExpense'e dönüştürülebilir.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.rules_engine import detect_subscriptions, workspace_scope  # M70
from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id, scope_filter  # M70 workspace scoping
from app.models import User, RecurringExpense, Account

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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M70
) -> SubscriptionsResponse:
    """İşlem geçmişinden tekrarlayan abonelikleri tespit eder (salt okuma)."""
    with workspace_scope(ws_id):  # M70: abonelik tespiti aktif workspace işlemlerinden
        return detect_subscriptions(user.id, date.today(), db, lookback_days=lookback_days)


class ToRecurringRequest(BaseModel):
    isim: str = Field(..., min_length=1, max_length=100)
    aylik_tutar: float = Field(..., gt=0)
    account_id: int
    day_of_month: int = Field(..., ge=1, le=31)
    category: str = Field("abonelik", max_length=50)


@router.post("/to-recurring", status_code=status.HTTP_201_CREATED)
def to_recurring(
    payload: ToRecurringRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M70
):
    """
    Tespit edilen bir aboneliği DÜZENLİ GİDER'e (RecurringExpense) çevirir — böylece bütçe/
    hatırlatma/otomasyon kapsamına girer (detect→act döngüsü tamamlanır). Kullanıcı tetikler.
    Aynı isimde aktif düzenli gider varsa 409.
    """
    acc = db.query(Account).filter(
        Account.id == payload.account_id, scope_filter(Account, user.id, ws_id)).first()  # M70
    if not acc:
        raise HTTPException(404, f"Hesap bulunamadi (id={payload.account_id})")
    dup = db.query(RecurringExpense).filter(
        scope_filter(RecurringExpense, user.id, ws_id), RecurringExpense.name == payload.isim,  # M70
        RecurringExpense.is_active == True,  # noqa: E712
    ).first()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail=f"'{payload.isim}' için zaten aktif düzenli gider var (id={dup.id}).")
    exp = RecurringExpense(
        user_id=user.id, workspace_id=ws_id, name=payload.isim, amount=payload.aylik_tutar,  # M70
        account_id=payload.account_id, category=payload.category, day_of_month=payload.day_of_month,
        is_active=True, notes="Abonelik denetçisinden dönüştürüldü (FEAT-006)",
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return {"id": exp.id, "name": exp.name, "amount": exp.amount, "day_of_month": exp.day_of_month}
