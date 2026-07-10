"""
User endpoint'leri (3):
- GET /api/user        - Mevcut kullaniciyi getir
- POST /api/user       - Ilk kurulum (sadece kullanici yoksa)
- PUT /api/user        - Isim guncelle

Tek-kullanici MVP. Bu router multi-user'a hazir ama simdilik tek kayit kuralin.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.serializers import UtcDateTime  # BUG #092: datetime UTC suffix
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import User

router = APIRouter(prefix="/api/user", tags=["user"])


# ============================================================
# SCHEMAS (router-yerel, schemas.py'yi kirletmeyiz)
# ============================================================

class UserOut(BaseModel):
    id: int
    name: str
    created_at: UtcDateTime

    class Config:
        from_attributes = True


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