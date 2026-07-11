"""
Envelope (kategori bütçe zarfı) endpoint'leri — FEAT-001 (YNAB/Actual Budget zarf yöntemi).

- GET    /api/envelopes            - Zarfları BU AY durumuyla listele (rules_engine hesabı)
- POST   /api/envelopes            - Yeni zarf (kategori + aylık bütçe)
- PUT    /api/envelopes/{id}       - Güncelle (tutar/aktiflik)
- DELETE /api/envelopes/{id}       - Sil

Harcama ayrı tutulmaz; rules_engine.calculate_envelopes bu ayın Transaction'larından türetir.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.serializers import UtcDateTime
from app.dependencies import get_db, get_current_user
from app.models import User, Envelope
from app.rules_engine import calculate_envelopes

router = APIRouter(prefix="/api/envelopes", tags=["envelopes"])


class EnvelopeCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    monthly_amount: Decimal = Field(..., gt=0)
    notes: Optional[str] = None


class EnvelopeUpdate(BaseModel):
    monthly_amount: Optional[Decimal] = Field(None, gt=0)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class EnvelopeOut(BaseModel):
    id: int
    category: str
    monthly_amount: Decimal
    is_active: bool
    notes: Optional[str] = None
    created_at: UtcDateTime

    model_config = {"from_attributes": True}


@router.get("")
def list_envelopes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Zarfları BU AY durumuyla döner: kayıtlar + calculate_envelopes özeti (harcanan/kalan/aşıldı)."""
    kayitlar = db.query(Envelope).filter(Envelope.user_id == user.id).order_by(Envelope.category).all()
    return {
        "envelopes": [EnvelopeOut.model_validate(e).model_dump() for e in kayitlar],
        "durum": calculate_envelopes(user.id, date.today(), db),
    }


@router.post("", response_model=EnvelopeOut, status_code=status.HTTP_201_CREATED)
def create_envelope(
    payload: EnvelopeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EnvelopeOut:
    """Yeni kategori bütçe zarfı. (user, category) tekildir — aynı kategori iki kez eklenemez."""
    existing = db.query(Envelope).filter(
        Envelope.user_id == user.id, Envelope.category == payload.category,
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail=f"'{payload.category}' için zarf zaten var (id={existing.id}).")
    env = Envelope(user_id=user.id, category=payload.category,
                   monthly_amount=payload.monthly_amount, notes=payload.notes)
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


@router.put("/{envelope_id}", response_model=EnvelopeOut)
def update_envelope(
    envelope_id: int,
    payload: EnvelopeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EnvelopeOut:
    env = db.query(Envelope).filter(
        Envelope.id == envelope_id, Envelope.user_id == user.id,
    ).first()
    if not env:
        raise HTTPException(404, f"Zarf bulunamadi (id={envelope_id})")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(env, k, v)
    db.commit()
    db.refresh(env)
    return env


@router.delete("/{envelope_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_envelope(
    envelope_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    env = db.query(Envelope).filter(
        Envelope.id == envelope_id, Envelope.user_id == user.id,
    ).first()
    if not env:
        raise HTTPException(404, f"Zarf bulunamadi (id={envelope_id})")
    db.delete(env)
    db.commit()
    return None
