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
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from app.serializers import UtcDateTime  # BUG #092: datetime UTC suffix
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id, scope_filter, require_write  # M43 workspace scoping
from app.user_rules import RULE_TYPES  # BUG #192: tek kaynak
from app.models import User, MasterCheckpoint, CheckpointType

router = APIRouter(prefix="/api/checkpoints", tags=["checkpoints"], dependencies=[Depends(require_write())])


# ============================================================
# SCHEMAS
# ============================================================

class CheckpointBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    # BUG #177 (P2): SINIRSIZDI ve icerigi SISTEM PROMPT'una gomuluyor (coach context) —
    # dev metin hem DB'yi sisirir hem her koc cagrisinda maliyeti/baglami patlatir.
    description: str = Field(..., min_length=1, max_length=2000)
    checkpoint_type: CheckpointType
    priority: int = Field(2, ge=1, le=3, description="1=en yuksek, 3=en dusuk")
    is_active: bool = True
    # BUG #192 (P3.5/H3): opsiyonel YAPILANDIRILMIS kural. Doldurulursa aksiyon
    # uygulanmadan once kod seviyesinde dayatilir (app/user_rules.py).
    rule_type: Optional[str] = Field(None, description="min_cash_floor | account_untouchable | max_single_expense")
    rule_params: Optional[dict] = Field(None, description='ornek: {"amount": 5000}')


    @model_validator(mode="after")
    def _kural_tutarli(self):
        """BUG #192: kural tipi bilinen olmali ve gerekli parametreyi tasimali.

        Sessiz kabul edilen bozuk kural = kullanicinin korundugunu SANMASI (en kotu hata).
        """
        if self.rule_type is None:
            return self
        if self.rule_type not in RULE_TYPES:
            raise ValueError(f"Bilinmeyen kural tipi. Gecerli: {', '.join(RULE_TYPES)}")
        params = self.rule_params or {}
        gerekli = {"min_cash_floor": "amount", "max_single_expense": "amount",
                   "account_untouchable": "account_id"}[self.rule_type]
        if gerekli not in params:
            raise ValueError(f"'{self.rule_type}' kurali icin '{gerekli}' parametresi zorunlu")
        deger = params[gerekli]
        if not isinstance(deger, (int, float)) or isinstance(deger, bool) or deger <= 0:
            raise ValueError(f"'{gerekli}' pozitif bir sayi olmali")
        return self


class CheckpointCreate(CheckpointBase):
    pass


class CheckpointUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1)
    checkpoint_type: Optional[CheckpointType] = None
    priority: Optional[int] = Field(None, ge=1, le=3)
    is_active: Optional[bool] = None
    rule_type: Optional[str] = None       # BUG #192
    rule_params: Optional[dict] = None    # BUG #192


class CheckpointOut(CheckpointBase):
    id: int
    created_at: UtcDateTime

    @field_validator("rule_params", mode="before")
    @classmethod
    def _params_coz(cls, v):
        """DB'de JSON metni tutulur; API sozlesmesi dict'tir."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    model_config = {"from_attributes": True}  # BUG #118: Pydantic V2 (V1 class Config deprecated)


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.get("", response_model=List[CheckpointOut])
def list_checkpoints(
    active_only: bool = Query(True, description="True (default): sadece aktif kirmizi cizgiler"),
    checkpoint_type: Optional[CheckpointType] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> List[CheckpointOut]:
    """
    Kirmizi cizgileri listele. Default sadece aktif olanlar; tarihce icin ?active_only=false.
    """
    q = db.query(MasterCheckpoint).filter(scope_filter(MasterCheckpoint, user.id, ws_id))
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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> CheckpointOut:
    """Yeni Master Checkpoint olustur."""
    veri = payload.model_dump()
    if veri.get("rule_params") is not None:
        veri["rule_params"] = json.dumps(veri["rule_params"])  # BUG #192: DB'de Text
    cp = MasterCheckpoint(user_id=user.id, workspace_id=ws_id, **veri)
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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> CheckpointOut:
    """Master Checkpoint guncelle."""
    cp = db.query(MasterCheckpoint).filter(
        MasterCheckpoint.id == cp_id, scope_filter(MasterCheckpoint, user.id, ws_id)
    ).first()
    if not cp:
        raise HTTPException(404, f"Checkpoint bulunamadi (id={cp_id})")

    update_data = payload.model_dump(exclude_unset=True)
    if isinstance(update_data.get("rule_params"), dict):
        update_data["rule_params"] = json.dumps(update_data["rule_params"])  # BUG #192
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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> None:
    """
    Default: SOFT DELETE — is_active=False yapar, tarihce kalir.
    ?hard=true ile gercek silme.

    KORUMA: Priority=1 + type=red_line olan checkpoint'ler ?hard=true ile bile
    silinmesin — bunlar MC1 emanet gibi kritik kurallar, yanlislikla kaybolmamali.
    """
    cp = db.query(MasterCheckpoint).filter(
        MasterCheckpoint.id == cp_id, scope_filter(MasterCheckpoint, user.id, ws_id)
    ).first()
    if not cp:
        raise HTTPException(404, f"Checkpoint bulunamadi (id={cp_id})")

    # W3-039 (RCH-002): sistem (Master) checkpoint'ler VEYA priority-1 red_line'lar hard
    # delete edilemez. Eskiden yalnız priority-1+red_line korunuyordu → MC4/5/6/8 (type=rule)
    # ?hard=true ile silinebiliyordu. Artık is_system flag'i format/priority'den bağımsız korur.
    is_protected = cp.is_system or (
        cp.priority == 1 and cp.checkpoint_type == CheckpointType.red_line
    )
    if hard and is_protected:
        raise HTTPException(
            status_code=403,
            detail=f"Sistem/kritik checkpoint hard delete edilemez "
                   f"('{cp.title}'). Pasiflestirmek icin ?hard=false kullanin.",
        )

    if hard:
        db.delete(cp)
    else:
        cp.is_active = False

    db.commit()
    return None