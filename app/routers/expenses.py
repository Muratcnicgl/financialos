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
from app.serializers import UtcDateTime  # BUG #092: datetime UTC suffix
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id, scope_filter, require_write  # M43 workspace scoping
from app.models import User, RecurringExpense, Account, PendingAction, ActionStatus
from app.schema_types import FinansTutar, FinansOptTutar  # SEC-032: sonlu/pozitif tutar

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expenses/recurring", tags=["recurring-expenses"], dependencies=[Depends(require_write())])


# ============================================================
# SCHEMAS
# ============================================================

class ExpenseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    amount: FinansTutar  # SEC-032: gt=0 + sonlu + üst sınır
    account_id: int = Field(..., description="Ödeme yapılacak hesap (kart veya nakit)")
    category: Optional[str] = Field(None, max_length=50)
    day_of_month: int = Field(..., ge=1, le=31)
    is_active: bool = True
    notes: Optional[str] = Field(None, max_length=2000)  # BUG #181


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    amount: FinansOptTutar = None  # SEC-032
    account_id: Optional[int] = None
    category: Optional[str] = Field(None, max_length=50)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=2000)  # BUG #181


class ExpenseOut(ExpenseBase):
    id: int
    created_at: UtcDateTime
    last_triggered_year_month: Optional[str] = None

    model_config = {"from_attributes": True}  # BUG #118: Pydantic V2 (V1 class Config deprecated)


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.get("", response_model=List[ExpenseOut])
def list_expenses(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> List[ExpenseOut]:
    """Düzenli giderleri listele."""
    q = db.query(RecurringExpense).filter(scope_filter(RecurringExpense, user.id, ws_id))  # M43
    if active_only:
        q = q.filter(RecurringExpense.is_active == True)
    return q.order_by(RecurringExpense.day_of_month, RecurringExpense.id).all()


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> ExpenseOut:
    """Yeni düzenli gider kaydı (Netflix, kira, fatura vb.)."""
    # account_id kullanıcıya ait mi doğrula
    acc = db.query(Account).filter(
        Account.id == payload.account_id,
        scope_filter(Account, user.id, ws_id),  # M43
    ).first()
    if not acc:
        raise HTTPException(404, f"Hesap bulunamadi: id={payload.account_id}")

    exp = RecurringExpense(user_id=user.id, workspace_id=ws_id, **payload.model_dump())  # M43
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> ExpenseOut:
    """Düzenli gideri güncelle. is_active=False ile pasifleştir, True ile aktive et."""
    exp = db.query(RecurringExpense).filter(
        RecurringExpense.id == expense_id,
        scope_filter(RecurringExpense, user.id, ws_id),  # M43
    ).first()
    if not exp:
        raise HTTPException(404, f"Gider bulunamadi: id={expense_id}")
    update_data = payload.model_dump(exclude_unset=True)
    # BUG #088 fix: create account_id sahipliğini doğruluyor (line 87-92) ama update
    # doğrulamadan setattr ediyordu → başka kullanıcının/var olmayan hesabına bağlanıp
    # trigger-due o hesaba propose_action üretebiliyordu. Simetrik doğrulama eklendi.
    if "account_id" in update_data and update_data["account_id"] is not None:
        target = db.query(Account).filter(
            Account.id == update_data["account_id"],
            scope_filter(Account, user.id, ws_id),  # M43
        ).first()
        if not target:
            raise HTTPException(404, "Hedef hesap bulunamadi veya size ait degil.")
    for k, v in update_data.items():
        setattr(exp, k, v)
    db.commit()
    db.refresh(exp)
    return exp


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> None:
    """Düzenli gideri sil. Soft-delete için PUT yerine is_active=false kullan."""
    exp = db.query(RecurringExpense).filter(
        RecurringExpense.id == expense_id,
        scope_filter(RecurringExpense, user.id, ws_id),  # M43
    ).first()
    if not exp:
        raise HTTPException(404, f"Gider bulunamadi: id={expense_id}")
    db.delete(exp)
    db.commit()


@router.post("/trigger-due")
def trigger_due_expenses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
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

    # BUG #071 fix (P0-16): day_of_month'u ay uzunluğuna clamp'le. 29/30/31 kısa aylarda
    # (Şubat/Nisan/Haziran/Eylül/Kasım) `day_of_month <= today.day` HİÇ True olmuyordu →
    # o ay sessizce atlanıp telafi de edilmiyordu.
    import calendar
    last_day = calendar.monthrange(today.year, today.month)[1]

    exps = db.query(RecurringExpense).filter(
        scope_filter(RecurringExpense, user.id, ws_id),  # M43
        RecurringExpense.is_active == True,
    ).all()

    triggered = []
    for exp in exps:
        effective_day = min(exp.day_of_month, last_day)
        if effective_day > today.day:
            continue  # bu ay vadesi henüz gelmedi
        # BUG #047 çift kontrol:
        # (1) Bu ay zaten EXECUTED olarak işaretlenmiş mi (last_triggered execute'te set edilir)
        if exp.last_triggered_year_month == year_month:
            continue
        # (2) Bu kayıt için zaten pending var mı
        existing_pending = db.query(PendingAction).filter(
            PendingAction.user_id == user.id,  # scope-exempt: pending dedup (user-level, trigger-due)
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
            # BUG #070 fix (P0-15): last_triggered BURADA set EDİLMEZ — execute'te
            # (_mark_recurring_triggered) set edilir; reddedilen/başarısız gider re-triggerable kalır.
            pending.source_recurring_id = exp.id
            pending.source_recurring_type = "expense"
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
