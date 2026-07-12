"""
İstek listesi / 24-saat impuls bekleme — FEAT-032 (davranışsal finans; impuls harcamayı kırar).

- GET    /api/wishlist            - Bekleyen istekler (24h+ geçenler review'a hazır işaretli)
- POST   /api/wishlist            - Yeni istek (item + tahmini tutar) — niyet kaydı, mutasyon DEĞİL
- POST   /api/wishlist/{id}/resolve?status=bought|dismissed  - İsteği kapat

Alım gerçekleşirse kullanıcı 'bought' işaretler + ayrıca işlemi normal akışla girer
(propose_action → onay → execute). Liste ekleme KURAL SIFIR'a uygundur (gerçekleşmiş eylem değil).
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.serializers import UtcDateTime
from app.dependencies import get_db, get_current_user
from app.models import User, WishlistItem

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])

REVIEW_AFTER_HOURS = 24  # 24-saat kuralı — bu süre sonra koç "hâlâ istiyor musun?" sorar


class WishlistCreate(BaseModel):
    item: str = Field(..., min_length=1, max_length=200)
    amount: Decimal = Field(..., gt=0)
    note: Optional[str] = None


class WishlistOut(BaseModel):
    id: int
    item: str
    amount: Decimal
    note: Optional[str] = None
    status: str
    created_at: UtcDateTime
    hazir: bool          # 24h+ geçti mi (review zamanı)

    model_config = {"from_attributes": True}


def _to_out(w: WishlistItem, now: datetime) -> WishlistOut:
    hazir = (now - w.created_at) >= timedelta(hours=REVIEW_AFTER_HOURS) if w.created_at else False
    return WishlistOut(
        id=w.id, item=w.item, amount=w.amount, note=w.note, status=w.status,
        created_at=w.created_at, hazir=hazir,
    )


@router.get("", response_model=dict)
def list_wishlist(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = datetime.utcnow()
    rows = (
        db.query(WishlistItem)
        .filter(WishlistItem.user_id == user.id, WishlistItem.status == "pending")
        .order_by(WishlistItem.created_at.asc())
        .all()
    )
    items = [_to_out(w, now) for w in rows]
    return {
        "items": items,
        "bekleyen_adet": len(items),
        "review_adet": sum(1 for i in items if i.hazir),   # 24h+ geçen, gözden geçirilecek
    }


@router.post("", response_model=WishlistOut, status_code=201)
def add_wishlist(payload: WishlistCreate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    w = WishlistItem(user_id=user.id, item=payload.item, amount=payload.amount,
                     note=payload.note, status="pending")
    db.add(w)
    db.commit()
    db.refresh(w)
    return _to_out(w, datetime.utcnow())


@router.post("/{item_id}/resolve", response_model=WishlistOut)
def resolve_wishlist(item_id: int, status: str = Query(..., pattern="^(bought|dismissed)$"),
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    w = db.query(WishlistItem).filter(
        WishlistItem.id == item_id, WishlistItem.user_id == user.id).first()
    if not w:
        raise HTTPException(status_code=404, detail="İstek bulunamadı")
    if w.status != "pending":
        raise HTTPException(status_code=409, detail="İstek zaten kapatılmış")
    w.status = status
    w.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(w)
    return _to_out(w, datetime.utcnow())
