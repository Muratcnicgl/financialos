"""
MasterCheckpoint endpoint'leri (4):
- GET    /api/checkpoints           - Listele (?active_only, ?type)
- POST   /api/checkpoints           - Yeni kirmizi cizgi/kural
- PUT    /api/checkpoints/{id}      - Guncelle
- DELETE /api/checkpoints/{id}      - SOFT DELETE (is_active=False)

ONEMLI: Master Checkpoint'ler kirmizi cizgilerdir. DELETE GERCEK SILME YAPMAZ -
sadece is_active=False yapar. Boylece kullanici 'sildim' dedikten 6 ay sonra
'aslinda dogru karardi' diyebilir. Tarih kalir.
Eger gercek silme gerekirse: PUT ile pasiflestir, sonra db'den manuel temizle.

MC1 (emanet) korumasi: Priority 1 + checkpoint_type=red_line olanlar silinmek
istenirse engelleniyor — bu MC1 gibi kritik kurallari yanlislikla devre dis
birakmayi onler.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import User, MasterCheckpoint, CheckpointType

router = APIRouter(prefix="/api/checkpoints", tags=["checkpoints"])


# ============================================================
# SCHEMAS
# ============================================================

class CheckpointBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    checkpoint_type: CheckpointType
    priority: int = Field(2, ge=1, le=3, description="1=en yuksek, 3=en dusuk")
    is_active: bool = True


class CheckpointCreate(CheckpointBase):
    pass


class CheckpointUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1)
    checkpoint_type: Optional[CheckpointType] = None
    priority: Optional[int] = Field(None, ge=1, le=3)
    is_active: Optional[bool] = None


class CheckpointOut(CheckpointBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.get("", response_model=List[CheckpointOut])
def list_checkpoints(
    active_only: bool = Query(True, description="True (default): sadece aktif kirmizi cizgiler"),
    checkpoint_type: Optional[CheckpointType] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[CheckpointOut]:
    """
    Kirmizi cizgileri listele. Default sadece aktif olanlar; tarihce icin ?active_only=false.
    """
    q = db.query(MasterCheckpoint).filter(MasterCheckpoint.user_id == user.id)
    if active_only:
        q = q.filter(MasterCheckpoint.is_active == True)
    if checkpoint_type:
        q = q.filter(MasterCheckpoint.checkpoint_type == checkpoint_type)
    return q.order_by(MasterCheckpoint.priority.asc(), MasterCheckpoint.id.asc()).all()


@router.post("", response_model=CheckpointOut, status_code=status.HTTP_201_CREATED)
def create_checkpoint(
    payload: CheckpointCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CheckpointOut:
    """Yeni Master Checkpoint olustur."""
    cp = MasterCheckpoint(user_id=user.id, **payload.model_dump())
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


@router.put("/{cp_id}", response_model=CheckpointOut)
def update_checkpoint(
    cp_id: int,
    payload: CheckpointUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CheckpointOut:
    """Master Checkpoint guncelle."""
    cp = db.query(MasterCheckpoint).filter(
        MasterCheckpoint.id == cp_id, MasterCheckpoint.user_id == user.id
    ).first()
    if not cp:
        raise HTTPException(404, f"Checkpoint bulunamadi (id={cp_id})")

    update_data = payload.model_dump(exclude_unset=True)
    # BUG #067 fix (RCH-003): korunan checkpoint'in (priority=1 + red_line) priority/
    # checkpoint_type alanlari degistirilip sonra ?hard=true ile silinerek Master Checkpoint
    # enforcement'i (emanet dokunulmazligi vb.) iki adimda delinmesin. delete_checkpoint ile
    # ayni koruma burada da uygulanir — korunan kayitta bu iki alan degistirilemez.
    is_protected = (cp.priority == 1 and cp.checkpoint_type == CheckpointType.red_line)
    if is_protected and ("priority" in update_data or "checkpoint_type" in update_data):
        raise HTTPException(
            status_code=403,
            detail=f"Korunan checkpoint'in (MC{cp_id} '{cp.title}') priority/checkpoint_type "
                   f"alanlari degistirilemez (Master Checkpoint enforcement).",
        )
    for k, v in update_data.items():
        setattr(cp, k, v)

    db.commit()
    db.refresh(cp)
    return cp


@router.delete("/{cp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checkpoint(
    cp_id: int,
    hard: bool = Query(
        False,
        description="True: gercek silme. False (default): is_active=False (soft delete).",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """
    Default: SOFT DELETE — is_active=False yapar, tarihce kalir.
    ?hard=true ile gercek silme.

    KORUMA: Priority=1 + type=red_line olan checkpoint'ler ?hard=true ile bile
    silinmesin — bunlar MC1 emanet gibi kritik kurallar, yanlislikla kaybolmamali.
    """
    cp = db.query(MasterCheckpoint).filter(
        MasterCheckpoint.id == cp_id, MasterCheckpoint.user_id == user.id
    ).first()
    if not cp:
        raise HTTPException(404, f"Checkpoint bulunamadi (id={cp_id})")

    if hard and cp.priority == 1 and cp.checkpoint_type == CheckpointType.red_line:
        raise HTTPException(
            status_code=403,
            detail=f"Priority 1 red_line checkpoint hard delete edilemez "
                   f"(MC{cp_id} '{cp.title}'). Pasiflestirmek icin ?hard=false kullanin.",
        )

    if hard:
        db.delete(cp)
    else:
        cp.is_active = False

    db.commit()
    return None