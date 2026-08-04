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
from app.user_prefs import user_today  # BUG #197: kullanici saat dilimi
from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id, scope_filter, require_write  # M43, require_write
from app.models import User, Envelope, Account, AccountType
from app.rules_engine import calculate_envelopes, workspace_scope  # M43

router = APIRouter(prefix="/api/envelopes", tags=["envelopes"], dependencies=[Depends(require_write())])


class EnvelopeCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    monthly_amount: Decimal = Field(..., gt=0)
    notes: Optional[str] = Field(None, max_length=2000)  # BUG #181


class EnvelopeUpdate(BaseModel):
    monthly_amount: Optional[Decimal] = Field(None, gt=0)
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=2000)  # BUG #181


class EnvelopeOut(BaseModel):
    id: int
    category: str
    monthly_amount: Decimal
    is_active: bool
    notes: Optional[str] = Field(None, max_length=2000)  # BUG #181
    created_at: UtcDateTime

    model_config = {"from_attributes": True}


@router.get("")
def list_envelopes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """Zarfları BU AY durumuyla döner: kayıtlar + calculate_envelopes özeti (harcanan/kalan/aşıldı)."""
    kayitlar = db.query(Envelope).filter(scope_filter(Envelope, user.id, ws_id)).order_by(Envelope.category).all()
    with workspace_scope(ws_id):  # M43: durum özeti aktif workspace'ten
        durum = calculate_envelopes(user.id, user_today(user), db)  # BUG #197
    # FEAT-002 (Ready to Assign): zarflara taahhüt edilmemiş nakit
    nakit = sum(float(a.balance) for a in db.query(Account).filter(
        scope_filter(Account, user.id, ws_id), Account.account_type == AccountType.cash).all())
    taahhut = sum(max(0.0, z["kalan"]) for z in durum["zarflar"])
    return {
        "envelopes": [EnvelopeOut.model_validate(e).model_dump() for e in kayitlar],
        "durum": durum,
        "atanmamis_nakit": round(nakit - taahhut, 2),
    }


@router.post("", response_model=EnvelopeOut, status_code=status.HTTP_201_CREATED)
def create_envelope(
    payload: EnvelopeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> EnvelopeOut:
    """Yeni kategori bütçe zarfı. (user, category) tekildir — aynı kategori iki kez eklenemez."""
    existing = db.query(Envelope).filter(
        scope_filter(Envelope, user.id, ws_id), Envelope.category == payload.category,
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail=f"'{payload.category}' için zarf zaten var (id={existing.id}).")
    env = Envelope(user_id=user.id, workspace_id=ws_id, category=payload.category,
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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> EnvelopeOut:
    env = db.query(Envelope).filter(
        Envelope.id == envelope_id, scope_filter(Envelope, user.id, ws_id),
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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> None:
    env = db.query(Envelope).filter(
        Envelope.id == envelope_id, scope_filter(Envelope, user.id, ws_id),
    ).first()
    if not env:
        raise HTTPException(404, f"Zarf bulunamadi (id={envelope_id})")
    db.delete(env)
    db.commit()
    return None
