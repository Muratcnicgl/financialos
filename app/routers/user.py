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
from app.data_subject import disa_aktar  # BUG #243: KVKK export TEK KAYNAK
from app.models import (
    User, Account, Transaction, RecurringIncome, RecurringExpense, PersonalDebt,
    Goal, Envelope, MasterCheckpoint, NetWorthSnapshot, CoachMemory, CoachInsight,
    # KVKK/egemenlik tamlığı: kullanıcının eylem/karar/hedef-izleme kayıtları da dahil.
    PendingAction, ActionHistory, DecisionJournal, ReasoningTrace, ApiCallLog,
    DemoDataMarker,  # BUG #194
    GoalAllocation, GoalRule, WishlistItem,
    Workspace, WorkspaceMembership,  # M40 (ADR-036) — KVKK tamlığı
    Feedback,  # FEAT-033 — KVKK tamlığı
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
    # H4 (BUG #197): kisisellestirme — None = sunucu/urun varsayilani
    timezone: Optional[str] = None
    currency: Optional[str] = None
    locale: Optional[str] = None
    created_at: UtcDateTime

    model_config = {"from_attributes": True}  # BUG #118: Pydantic V2 (V1 class Config deprecated)


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    # H4: gecersiz saat dilimi SESSIZCE yanlis tarih uretmesin -> yazarken dogrulanir
    timezone: Optional[str] = Field(None, max_length=40)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    locale: Optional[str] = Field(None, max_length=10)


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
    # BUG #174 (P2): bu uç kimlik doğrulaması İSTEMİYORDU (tek-kullanıcı kurulum kalıntısı).
    # Çok-kullanıcı/AUTH açık kurulumda kayıt YOLU /api/auth/register'dır; taze bir
    # instance'ta yabancı birinin id=1 kullanıcıyı yaratmasına izin verilmez.
    from app import auth as _auth
    if _auth.auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcı oluşturma kapalı — kayıt için POST /api/auth/register kullanın.",
        )
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
    """Mevcut kullanicinin adini ve tercihlerini guncelle (H4)."""
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.timezone is not None:
        # Gecersiz TZ kabul edilirse kullanici "ayarladim" sanir ama tarihler yanlis kalir.
        from zoneinfo import ZoneInfo
        try:
            ZoneInfo(payload.timezone)
        except Exception:
            raise HTTPException(422, f"Gecersiz saat dilimi: {payload.timezone}")
        user.timezone = payload.timezone
    if payload.currency is not None:
        user.currency = payload.currency.upper()
    if payload.locale is not None:
        user.locale = payload.locale
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
    dışa aktarabilir, kilitlenmez.

    BUG #243 fix (D26/D28): gövde artık burada DEĞİL — export'un tek uygulaması
    `app/data_subject.disa_aktar`. Eskiden iki ayrı uygulama vardı (bu uç elle bakılan bir
    liste, `/api/users/me/export` ise ilişki-türetmeli) ve ayrışmışlardı: UI'nin kullandığı
    uç `goal_allocations`/`goal_rules`'u hiç dökmüyor, ikisi de kullanıcının bcrypt şifre
    hash'ini ve OAuth kimliğini dosyaya yazıyordu.
    """
    return disa_aktar(db, user)
