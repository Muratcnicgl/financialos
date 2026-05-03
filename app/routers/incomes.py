"""
RecurringIncome endpoint'leri (4):
- GET    /api/incomes           - Listele (?active_only=true|false)
- POST   /api/incomes           - Yeni duzenli gelir
- PUT    /api/incomes/{id}      - Guncelle (is_active=False ile pasiflestir)
- DELETE /api/incomes/{id}      - Sil

Mukemmellestirici: Burada DELETE de var ama is_active=False ile soft-delete tavsiye edilir.
KYK iptali gibi durumlar icin: gercek silme yerine pasiflestirme - tarihce kalir.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import User, RecurringIncome

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
    created_at: datetime

    class Config:
        from_attributes = True


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