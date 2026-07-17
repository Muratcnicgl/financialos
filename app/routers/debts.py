"""
PersonalDebt endpoint'leri (4):
- GET    /api/debts             - Listele (?direction, ?paid)
- POST   /api/debts             - Yeni borc/alacak
- PUT    /api/debts/{id}        - Guncelle (paid_date set ederek 'odendi' isaretleme)
- DELETE /api/debts/{id}        - Sil

Mukemmellestirici: PUT ile paid_date set edilirse is_paid otomatik True olur.
Frontend "Odendi" butonu basinca {"paid_date": "2026-05-05"} yollar yeter.
"""

from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from app.serializers import UtcDateTime  # BUG #092: datetime UTC suffix
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id, scope_filter  # M43 workspace scoping
from app.models import User, PersonalDebt, DebtDirection
from app.schema_types import FinansTutar, FinansOptTutar  # SEC-032: sonlu/pozitif tutar

router = APIRouter(prefix="/api/debts", tags=["debts"])


# ============================================================
# SCHEMAS
# ============================================================

class DebtBase(BaseModel):
    counterparty: str = Field(..., min_length=1, max_length=100)
    direction: DebtDirection
    amount: FinansTutar  # SEC-032: gt=0 + sonlu + üst sınır (inf/NaN/taşma reddedilir)
    description: Optional[str] = None
    due_date: Optional[date] = None


class DebtCreate(DebtBase):
    pass


class DebtUpdate(BaseModel):
    counterparty: Optional[str] = Field(None, min_length=1, max_length=100)
    amount: FinansOptTutar = None  # SEC-032
    description: Optional[str] = None
    due_date: Optional[date] = None
    paid_date: Optional[date] = None      # Set edilirse is_paid=True olur
    is_paid: Optional[bool] = None        # Manuel ovverride


class DebtOut(DebtBase):
    id: int
    is_paid: bool
    paid_date: Optional[date]
    created_at: UtcDateTime

    model_config = {"from_attributes": True}  # BUG #118: Pydantic V2 (V1 class Config deprecated)


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.get("", response_model=List[DebtOut])
def list_debts(
    direction: Optional[DebtDirection] = None,
    paid: Optional[bool] = Query(None, description="True: odenmis, False: odenmemis, None: hepsi"),
    counterparty: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> List[DebtOut]:
    """
    Borc/alacak listesi.
    ornek: GET /api/debts?direction=receivable&paid=false
    -> Tahsil edilmemis tum alacaklar (Efe alacaklari icin)
    """
    q = db.query(PersonalDebt).filter(scope_filter(PersonalDebt, user.id, ws_id))

    if direction:
        q = q.filter(PersonalDebt.direction == direction)
    if paid is not None:
        q = q.filter(PersonalDebt.is_paid == paid)
    if counterparty:
        q = q.filter(PersonalDebt.counterparty == counterparty)

    return q.order_by(PersonalDebt.due_date.asc().nulls_last(), PersonalDebt.id).all()


@router.post("", response_model=DebtOut, status_code=status.HTTP_201_CREATED)
def create_debt(
    payload: DebtCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> DebtOut:
    """Yeni borc/alacak ekle. is_paid default False."""
    debt = PersonalDebt(user_id=user.id, workspace_id=ws_id, **payload.model_dump())
    db.add(debt)
    db.commit()
    db.refresh(debt)
    return debt


@router.put("/{debt_id}", response_model=DebtOut)
def update_debt(
    debt_id: int,
    payload: DebtUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> DebtOut:
    """
    Guncelle. Mukemmellestirici akilli davranis:
    - paid_date verilirse is_paid otomatik True olur (kullanici sadece tarih girer)
    - is_paid=False verilirse paid_date otomatik None olur (geri al)
    """
    debt = db.query(PersonalDebt).filter(
        PersonalDebt.id == debt_id, scope_filter(PersonalDebt, user.id, ws_id)
    ).first()
    if not debt:
        raise HTTPException(404, f"Borc/alacak bulunamadi (id={debt_id})")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(debt, k, v)

    # Akilli senkronizasyon — BUG #106 fix: çelişkide (is_paid=False + paid_date verilmiş)
    # explicit is_paid KAZANIR ve tutarlılık HER durumda garanti edilir. Eskiden iki kural
    # sırayla çalışıp "is_paid=True ama paid_date=None" (ödendi ama tarih yok) üretebiliyordu.
    if "is_paid" in update_data:
        if update_data["is_paid"] is False:
            debt.paid_date = None
        elif debt.paid_date is None:
            debt.paid_date = date.today()  # ödendi işaretlendi ama tarih yok → bugün
    elif "paid_date" in update_data:
        debt.is_paid = update_data["paid_date"] is not None

    db.commit()
    db.refresh(debt)
    return debt


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_debt(
    debt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> None:
    """Borc/alacak kaydini sil."""
    debt = db.query(PersonalDebt).filter(
        PersonalDebt.id == debt_id, scope_filter(PersonalDebt, user.id, ws_id)
    ).first()
    if not debt:
        raise HTTPException(404, f"Borc/alacak bulunamadi (id={debt_id})")
    db.delete(debt)
    db.commit()
    return None