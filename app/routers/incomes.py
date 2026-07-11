"""
RecurringIncome endpoint'leri (4):
- GET    /api/incomes           - Listele (?active_only=true|false)
- POST   /api/incomes           - Yeni duzenli gelir
- PUT    /api/incomes/{id}      - Guncelle (is_active=False ile pasiflestir)
- DELETE /api/incomes/{id}      - Sil

Mukemmellestirici: Burada DELETE de var ama is_active=False ile soft-delete tavsiye edilir.
KYK iptali gibi durumlar icin: gercek silme yerine pasiflestirme - tarihce kalir.
"""

import json
import logging
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from app.serializers import UtcDateTime  # BUG #092: datetime UTC suffix
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import User, RecurringIncome, Account, AccountType, PendingAction, ActionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incomes", tags=["incomes"])


# ============================================================
# SCHEMAS
# ============================================================

class IncomeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0)
    day_of_month: int = Field(..., ge=1, le=31, description="Ayın kacinda gelir (1-31)")
    is_active: bool = True
    notes: Optional[str] = None


class IncomeCreate(IncomeBase):
    pass


class IncomeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    amount: Optional[float] = Field(None, gt=0)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class IncomeOut(IncomeBase):
    id: int
    created_at: UtcDateTime

    model_config = {"from_attributes": True}  # BUG #118: Pydantic V2 (V1 class Config deprecated)


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.get("", response_model=List[IncomeOut])
def list_incomes(
    active_only: bool = Query(False, description="True: sadece aktif gelirler"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[IncomeOut]:
    """Duzenli gelirleri listele. Default tumu, ?active_only=true ile filtrele."""
    q = db.query(RecurringIncome).filter(RecurringIncome.user_id == user.id)
    if active_only:
        q = q.filter(RecurringIncome.is_active == True)
    return q.order_by(RecurringIncome.day_of_month, RecurringIncome.id).all()


@router.post("", response_model=IncomeOut, status_code=status.HTTP_201_CREATED)
def create_income(
    payload: IncomeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> IncomeOut:
    """Yeni duzenli gelir kaydi (maaş, kira, abonelik vs)."""
    inc = RecurringIncome(user_id=user.id, **payload.model_dump())
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


@router.put("/{income_id}", response_model=IncomeOut)
def update_income(
    income_id: int,
    payload: IncomeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> IncomeOut:
    """
    Geliri guncelle. Mukemmellestirici kullanim ornegi:
    KYK iptal edildi -> PUT /api/incomes/2 {"is_active": false}
    Boylece tarihte kayit kalir, Cockpit gelirden saymaz.
    """
    inc = db.query(RecurringIncome).filter(
        RecurringIncome.id == income_id, RecurringIncome.user_id == user.id
    ).first()
    if not inc:
        raise HTTPException(404, f"Gelir bulunamadi (id={income_id})")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(inc, k, v)

    db.commit()
    db.refresh(inc)
    return inc


@router.post("/trigger-due")
def trigger_due_incomes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    A2 Recurring Trigger: Vadesi gelen duzenli gelirleri propose_action olarak olustur.
    Her aktif gelir icin: day_of_month <= bugun VE bu ay henuz tetiklenmemisse
    -> add_transaction (income) propose_action yarat.
    Dedup: last_triggered_year_month = '2026-05' ile ayni ay tekrar cagirmaz.
    """
    from app.action_executor import propose_action
    from app.action_executor import _fmt

    today = date.today()
    year_month = f"{today.year}-{today.month:02d}"

    cash_acc = db.query(Account).filter(
        Account.user_id == user.id,
        Account.account_type == AccountType.cash,
    ).first()
    if not cash_acc:
        return {"triggered": []}

    # BUG #071 fix (P0-16): day_of_month'u ay uzunluğuna clamp'le (kısa aylarda 31 atlanmasın).
    import calendar
    last_day = calendar.monthrange(today.year, today.month)[1]

    incomes = db.query(RecurringIncome).filter(
        RecurringIncome.user_id == user.id,
        RecurringIncome.is_active == True,
    ).all()

    triggered = []
    for inc in incomes:
        effective_day = min(inc.day_of_month, last_day)
        if effective_day > today.day:
            continue  # bu ay vadesi henüz gelmedi
        # BUG #047 çift kontrol:
        # (1) Bu ay zaten EXECUTED olarak işaretlenmiş mi (last_triggered execute'te set edilir)
        if inc.last_triggered_year_month == year_month:
            continue
        # (2) Bu kayıt için zaten pending var mı
        existing_pending = db.query(PendingAction).filter(
            PendingAction.user_id == user.id,
            PendingAction.source_recurring_id == inc.id,
            PendingAction.source_recurring_type == "income",
            PendingAction.status == ActionStatus.pending,
        ).first()
        if existing_pending:
            continue
        try:
            pending = propose_action(
                db=db,
                user_id=user.id,
                action_type="add_transaction",
                payload={
                    "account_id": cash_acc.id,
                    "amount": inc.amount,
                    "transaction_type": "income",
                    "category": inc.name.lower().replace(" ", "_"),
                    "description": f"{inc.name} — {today.strftime('%B %Y')}",
                    "transaction_date": today.isoformat(),
                },
                summary=f"{inc.name}: {_fmt(inc.amount)} TL geldi",
            )
            # BUG #070 fix (P0-15): last_triggered BURADA set EDİLMEZ — execute'te set edilir.
            pending.source_recurring_id = inc.id
            pending.source_recurring_type = "income"
            db.commit()
            triggered.append({
                "id": pending.id,
                "action_id": pending.id,
                "action_type": pending.action_type,
                "summary": pending.summary,
                "payload": json.loads(pending.payload),
                "warning": getattr(pending, "_warning_text", None),
            })
        except Exception as e:
            logger.error(f"trigger_due_incomes: {inc.name} hata: {e}")

    return {"triggered": triggered}


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(
    income_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Geliri tamamen sil. Soft-delete icin PUT ile is_active=false tercih edin."""
    inc = db.query(RecurringIncome).filter(
        RecurringIncome.id == income_id, RecurringIncome.user_id == user.id
    ).first()
    if not inc:
        raise HTTPException(404, f"Gelir bulunamadi (id={income_id})")
    db.delete(inc)
    db.commit()
    return None