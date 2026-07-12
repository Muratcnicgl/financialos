"""
User endpoint'leri (4):
- GET  /api/user        - Mevcut kullaniciyi getir
- POST /api/user        - Ilk kurulum (sadece kullanici yoksa)
- PUT  /api/user        - Isim guncelle
- GET  /api/user/export - TÜM kullanıcı verisinin JSON dökümü (veri egemenliği / KVKK)

Tek-kullanici MVP. Bu router multi-user'a hazir ama simdilik tek kayit kuralin.
"""

import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.serializers import UtcDateTime  # BUG #092: datetime UTC suffix
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import (
    User, Account, Transaction, RecurringIncome, RecurringExpense, PersonalDebt,
    Goal, Envelope, MasterCheckpoint, NetWorthSnapshot, CoachMemory, CoachInsight,
    # KVKK/egemenlik tamlığı: kullanıcının eylem/karar/hedef-izleme kayıtları da dahil.
    PendingAction, ActionHistory, DecisionJournal, ReasoningTrace, ApiCallLog,
    GoalAllocation, GoalRule, WishlistItem,
)

router = APIRouter(prefix="/api/user", tags=["user"])


def _json_val(v):
    """SQLAlchemy sütun değerini JSON-güvenli hale getirir."""
    if isinstance(v, enum.Enum):
        return v.value
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _row_to_dict(row) -> dict:
    return {c.name: _json_val(getattr(row, c.name)) for c in row.__table__.columns}


# ============================================================
# SCHEMAS (router-yerel, schemas.py'yi kirletmeyiz)
# ============================================================

class UserOut(BaseModel):
    id: int
    name: str
    created_at: UtcDateTime

    model_config = {"from_attributes": True}  # BUG #118: Pydantic V2 (V1 class Config deprecated)


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.get("", response_model=UserOut)
def get_user(user: User = Depends(get_current_user)) -> UserOut:
    """Mevcut kullaniciyi getir."""
    return user


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    """
    Ilk kurulum. Sadece DB'de hic kullanici yoksa olusturur.
    Daha sonra ek kullanici eklemek isteniyorsa burada degil, admin endpoint'inde olmali.
    """
    existing = db.query(User).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Kullanici zaten var (id={existing.id}, name={existing.name}). "
                   f"Ad degistirmek icin PUT /api/user kullanin.",
        )
    user = User(name=payload.name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("", response_model=UserOut)
def update_user(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserOut:
    """Mevcut kullanicinin adini guncelle."""
    if payload.name is not None:
        user.name = payload.name.strip()
    db.commit()
    db.refresh(user)
    return user


@router.get("/export")
def export_data(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Kullanıcının TÜM verisini tek JSON olarak döner — VERİ EGEMENLİĞİ ("Sovereign OS" kök
    vizyonu) + KVKK veri taşınabilirlik hakkı. Salt okuma; kullanıcı verisini istediği an
    dışa aktarabilir, kilitlenmez. Enum/tarih/Decimal JSON-güvenli serialize edilir.
    """
    def dump(model):
        return [_row_to_dict(r) for r in db.query(model).filter(model.user_id == user.id).all()]

    # GoalAllocation/GoalRule'da user_id YOK (DATA-011) → kullanıcının hedefleri üzerinden join.
    goal_ids = [g.id for g in db.query(Goal).filter(Goal.user_id == user.id).all()]

    def dump_by_goal(model):
        if not goal_ids:
            return []
        return [_row_to_dict(r) for r in db.query(model).filter(model.goal_id.in_(goal_ids)).all()]

    return {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "schema": "financialos-export-v1",
        "user": _row_to_dict(user),
        "accounts": dump(Account),
        "transactions": dump(Transaction),
        "recurring_incomes": dump(RecurringIncome),
        "recurring_expenses": dump(RecurringExpense),
        "personal_debts": dump(PersonalDebt),
        "goals": dump(Goal),
        "goal_allocations": dump_by_goal(GoalAllocation),  # KVKK: hedef katkı/çekim kayıtları
        "goal_rules": dump_by_goal(GoalRule),
        "envelopes": dump(Envelope),
        "wishlist_items": dump(WishlistItem),  # FEAT-032: istek listesi

        "master_checkpoints": dump(MasterCheckpoint),
        "net_worth_snapshots": dump(NetWorthSnapshot),
        "coach_memory": dump(CoachMemory),
        "coach_insights": dump(CoachInsight),
        # kullanıcının eylem/karar kayıtları (finansal geçmişin tam parçası)
        "pending_actions": dump(PendingAction),
        "action_history": dump(ActionHistory),
        "decision_journal": dump(DecisionJournal),
        # koç şeffaflığı (Sovereign OS: koçun para hakkındaki muhakemesi de kullanıcınındır)
        "reasoning_traces": dump(ReasoningTrace),
        "api_call_log": dump(ApiCallLog),
    }