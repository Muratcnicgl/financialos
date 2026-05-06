"""
RecurringExpense endpoint'leri (A3):
- GET    /api/expenses/recurring               - Listele
- POST   /api/expenses/recurring               - Yeni düzenli gider
- DELETE /api/expenses/recurring/{id}          - Sil (soft: is_active=False tercih)
- POST   /api/expenses/recurring/trigger-due   - Vadesi gelenleri propose_action olarak üret
"""

import json
import logging
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import User, RecurringExpense, Account, PendingAction, ActionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expenses/recurring", tags=["recurring-expenses"])


# ============================================================
# SCHEMAS
# ============================================================

class ExpenseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0)
    account_id: int = Field(..., description="Ödeme yapılacak hesap (kart veya nakit)")
    category: Optional[str] = Field(None, max_length=50)
    day_of_month: int = Field(..., ge=1, le=31)
    is_active: bool = True
    notes: Optional[str] = None


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseOut(ExpenseBase):
    id: int
    created_at: datetime
    last_triggered_year_month: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.get("", response_model=List[ExpenseOut])
def list_expenses(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ExpenseOut]:
    """Düzenli giderleri listele."""
    q = db.query(RecurringExpense).filter(RecurringExpense.user_id == user.id)
    if active_only:
        q = q.filter(RecurringExpense.is_active == True)
    return q.order_by(RecurringExpense.day_of_month, RecurringExpense.id).all()


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExpenseOut:
    """Yeni düzenli gider kaydı (Netflix, kira, fatura vb.)."""
    # account_id kullanıcıya ait mi doğrula
    acc = db.query(Account).filter(
        Account.id == payload.account_id,
        Account.user_id == user.id,
    ).first()
    if not acc:
        raise HTTPException(404, f"Hesap bulunamadi: id={payload.account_id}")

    exp = RecurringExpense(user_id=user.id, **payload.model_dump())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Düzenli gideri sil. Soft-delete için PUT yerine is_active=false kullan."""
    exp = db.query(RecurringExpense).filter(
        RecurringExpense.id == expense_id,
        RecurringExpense.user_id == user.id,
    ).first()
    if not exp:
        raise HTTPException(404, f"Gider bulunamadi: id={expense_id}")
    db.delete(exp)
    db.commit()


@router.post("/trigger-due")
def trigger_due_expenses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    A3 Recurring Trigger: Vadesi gelen düzenli giderler için propose_action oluştur.
    Dedup: last_triggered_year_month ile aynı ay tekrar tetiklenmez.
    account_id modelden gelir — _normalize_transaction_payload dokunmaz
    ("abonelik"/"fatura" _CARD_CATEGORIES'te değil, BUG #039 gereği açık account_id korunur).
    """
    from app.action_executor import propose_action
    from app.action_executor import _fmt

    today = date.today()
    year_month = f"{today.year}-{today.month:02d}"

    exps = db.query(RecurringExpense).filter(
        RecurringExpense.user_id == user.id,
        RecurringExpense.is_active == True,
        RecurringExpense.day_of_month <= today.day,
    ).all()

    triggered = []
    for exp in exps:
        # BUG #047 çift kontrol:
        # (1) Bu ay henüz tetiklenmemiş mi
        if exp.last_triggered_year_month == year_month:
            continue
        # (2) Bu kayıt için zaten pending var mı
        existing_pending = db.query(PendingAction).filter(
            PendingAction.user_id == user.id,
            PendingAction.source_recurring_id == exp.id,
            PendingAction.source_recurring_type == "expense",
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
                    "account_id": exp.account_id,
                    "amount": exp.amount,
                    "transaction_type": "expense",
                    "category": exp.category or exp.name.lower().replace(" ", "_"),
                    "description": f"{exp.name} — {today.strftime('%B %Y')}",
                    "transaction_date": today.isoformat(),
                    "is_card_expense": False,
                },
                summary=f"{exp.name}: {_fmt(exp.amount)} TL ödendi",
            )
            # BUG #047: source fields + last_triggered tek commit'te
            pending.source_recurring_id = exp.id
            pending.source_recurring_type = "expense"
            exp.last_triggered_year_month = year_month
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
            logger.error(f"trigger_due_expenses: {exp.name} hata: {e}")

    return {"triggered": triggered}
