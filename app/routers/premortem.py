"""
POST /api/premortem/{action_id}

Bekleyen bir aksiyon icin Klein (1989) premortem analizi uretir ve
DecisionJournal'a kaydeder. LLM cagrisi senkron — kullanici UI'da bekler.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cockpit_snapshot import build_cockpit_snapshot, compute_snapshot_hash
from app.dependencies import get_db, get_current_user
from app.models import ActionStatus, PendingAction, User
from app.premortem import (
    PremortemError,
    PremortemScenario,
    generate_premortem,
    persist_premortem,
)

router = APIRouter(prefix="/api/premortem", tags=["premortem"])
logger = logging.getLogger(__name__)


class PremortemResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    action_id: int
    scenarios: list[PremortemScenario]
    provider_used: str | None
    model_name: str | None
    persisted_decision_journal_id: int
    cached: bool


@router.post("/{action_id}", response_model=PremortemResponse)
def run_premortem(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bekleyen aksiyon icin 3-5 basarisizlik senaryosu uretir (Klein premortem).
    Sonuc DecisionJournal'a yazilir ve dogrudan doner.
    Sadece status=pending aksiyonlar kabul edilir.
    """
    action = db.execute(
        select(PendingAction).where(
            PendingAction.id == action_id,
            PendingAction.user_id == current_user.id,
        )
    ).scalar_one_or_none()

    if action is None:
        raise HTTPException(status_code=404, detail="Aksiyon bulunamadi")

    if action.status != ActionStatus.pending:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Premortem sadece bekleyen aksiyonlar icin calisir. "
                f"Su anki status: {action.status.value}"
            ),
        )

    # Payload'dan LLM'e verilecek baglam
    payload_dict: dict = {}
    if action.payload:
        try:
            payload_dict = json.loads(action.payload)
        except json.JSONDecodeError:
            payload_dict = {}

    action_context = {
        "action_type": action.action_type,
        "description": action.summary or "",
        "amount_tl": payload_dict.get("amount") or 0.0,
        "target": (
            payload_dict.get("account_name")
            or payload_dict.get("target")
            or payload_dict.get("debt_name")
            or "-"
        ),
        "rationale": payload_dict.get("rationale") or payload_dict.get("reason"),
    }

    snapshot = build_cockpit_snapshot(db, current_user.id)
    snapshot_hash = compute_snapshot_hash(snapshot)

    try:
        result = generate_premortem(
            action_id=action.id,
            action_context=action_context,
            cockpit_snapshot=snapshot,
        )
    except PremortemError as e:
        logger.error("premortem generation failed action_id=%s error=%s", action_id, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Premortem motoru su anda cevap veremedi: {e}",
        )

    dj = persist_premortem(db, action, current_user.id, result, snapshot_hash)

    logger.info(
        "premortem ok action_id=%s provider=%s scenarios=%d",
        action_id, result.provider_used, len(result.scenarios),
    )

    return PremortemResponse(
        action_id=result.action_id,
        scenarios=result.scenarios,
        provider_used=result.provider_used,
        model_name=result.model_name,
        persisted_decision_journal_id=dj.id,
        cached=False,
    )
