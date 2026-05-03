"""
Action endpoint'leri (4):
- GET  /api/actions/pending             - Onay bekleyen tum aksiyonlar
- POST /api/actions/{id}/approve        - Aksiyonu uygula (action_executor cagrisi)
- POST /api/actions/{id}/reject         - Aksiyonu reddet (DB'de status=rejected)
- GET  /api/actions/history             - Tum onaylanmis aksiyon log'u (Wave-1 yeni)

WAVE-1 MUKEMMELLESTIRICILER:
1. Approve sirasinda ActionHistory'e snapshot yaziliyor:
   - net_worth_before / net_worth_after
   - cash_before / cash_after
   - source = 'coach' (otomatik) veya 'user' (manuel hizli giristen)
2. History endpoint'i ile koc 'son 30 gunde 2 kez TLY satisi yaptin' diyebilir.
3. Reverted_by zinciri tablo'da hazir, V2'de geri al butonu olusturulacak.

NOT (2 Mayis 2026 fix): action_executor.execute_pending_action ve
reject_pending_action imzalari (db, action_id, user_id) seklinde — bu router
o sirayla cagiriyor. Hata yonetimi: executor exception firlatmaz, dict doner
({success: bool, error: str}) — router bu donusu kontrol eder.
"""

import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import (
    User, PendingAction, ActionStatus, ActionHistory, ActionSource,
)
from app.action_executor import execute_pending_action, reject_pending_action
from app.rules_engine import generate_cockpit

router = APIRouter(prefix="/api/actions", tags=["actions"])

logger = logging.getLogger(__name__)


# ============================================================
# SCHEMAS
# ============================================================

class PendingActionOut(BaseModel):
    id: int
    action_type: str
    summary: str
    payload: str          # JSON string (frontend kendi parse eder)
    warning: Optional[str] = None
    status: ActionStatus
    error_message: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RejectRequest(BaseModel):
    reason: Optional[str] = None


class ActionHistoryOut(BaseModel):
    id: int
    action_type: str
    summary: str
    payload: str
    source: ActionSource
    success: bool
    error_message: Optional[str] = None
    net_worth_before: Optional[float] = None
    net_worth_after: Optional[float] = None
    cash_before: Optional[float] = None
    cash_after: Optional[float] = None
    applied_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/pending", response_model=List[PendingActionOut])
def get_pending_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Onay bekleyen tum aksiyonlari listele."""
    actions = (
        db.query(PendingAction)
        .filter(
            PendingAction.user_id == current_user.id,
            PendingAction.status == ActionStatus.pending,
        )
        .order_by(PendingAction.created_at.desc())
        .all()
    )
    return actions


@router.post("/{action_id}/approve")
def approve_action(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aksiyonu onayla ve uygula. ActionHistory'e snapshot yaz."""
    from datetime import date

    # Oncelik: net worth snapshot al (execute oncesi)
    cockpit_before = generate_cockpit(current_user.id, date.today(), db)
    net_worth_before = cockpit_before.get("net_deger")
    cash_before = cockpit_before.get("nakit_kasa")

    # Pending action'i bul (execute icin)
    pending = (
        db.query(PendingAction)
        .filter(
            PendingAction.id == action_id,
            PendingAction.user_id == current_user.id,
        )
        .first()
    )
    if not pending:
        raise HTTPException(status_code=404, detail=f"Aksiyon bulunamadi: id={action_id}")

    result = execute_pending_action(db=db, action_id=action_id, user_id=current_user.id)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.get("error", "Aksiyon uygulanamadi."),
        )

    # Execute sonrasi snapshot
    cockpit_after = generate_cockpit(current_user.id, date.today(), db)
    net_worth_after = cockpit_after.get("net_deger")
    cash_after = cockpit_after.get("nakit_kasa")

    # ActionHistory'e yaz
    history_entry = ActionHistory(
        user_id=current_user.id,
        action_type=pending.action_type,
        payload=pending.payload,
        summary=pending.summary,
        source=ActionSource.coach,
        pending_action_id=pending.id,
        success=True,
        net_worth_before=net_worth_before,
        net_worth_after=net_worth_after,
        cash_before=cash_before,
        cash_after=cash_after,
    )
    db.add(history_entry)
    db.commit()

    return {
        "success": True,
        "action_id": action_id,
        "action_type": pending.action_type,
        "result": result.get("result"),
        "message": result.get("message"),  # BUG #031 fix: Türkçe özet → toast detail
        "net_worth_before": net_worth_before,
        "net_worth_after": net_worth_after,
        "cash_before": cash_before,
        "cash_after": cash_after,
    }


@router.post("/{action_id}/reject")
def reject_action(
    action_id: int,
    body: RejectRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aksiyonu reddet. DB'de status=rejected, hicbir degisiklik uygulanmaz."""
    reason = body.reason if body else None
    result = reject_pending_action(db=db, action_id=action_id, user_id=current_user.id, reason=reason)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Aksiyon reddetme basarisiz."))

    return result


@router.get("/history", response_model=List[ActionHistoryOut])
def get_action_history(
    limit: int = 50,
    action_type: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tum onaylanmis aksiyon gecmisi."""
    query = (
        db.query(ActionHistory)
        .filter(ActionHistory.user_id == current_user.id)
    )
    if action_type:
        query = query.filter(ActionHistory.action_type == action_type)

    entries = query.order_by(ActionHistory.applied_at.desc()).limit(limit).all()
    return entries









