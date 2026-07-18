"""
POST /api/simulate/{action_id}

Bekleyen bir aksiyon icin 3-Ufuklu Karar Masasi simulasyonu.
Improvement #022: T+0 (Bugun) / T+30 (Kisa) / T+90 (Orta) snapshot karsilastirmasi.

Plan v3 H2G3: 'Bugun/3 ay/3 yil ufuk gorunumu' - 3 yil engine kapsam disi
(Wave-3 multi-asset + enflasyon modeli gerektirir), su an T+90 ile kapatildi (ADR-022).

Felsefe: simulasyon karar VERMEZ, sadece 3 ufukta sonucu gosterir.
Son karar her zaman kullanicinin (ADR-001: kullanici karar verir, AI aciklar).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import ActionStatus, PendingAction, User
from app.simulation_engine import simulate_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulate", tags=["simulation"])


class HorizonSnapshot(BaseModel):
    """Tek bir ufuk icin snapshot."""
    model_config = ConfigDict(protected_namespaces=())

    label: str = Field(description="T+0 / T+30 / T+90")
    days: int
    nakit_kasa: float
    kart_borcu: float
    kredi_borcu: float
    yatirim_deger: float
    net_deger: float
    # BUG #082 fix (P0-10/RSI-001): reel_butce/daily_limit KALDIRILDI. simulation_engine
    # bu alanları üretmiyordu → HorizonSnapshot'ta hep 0.0 dönüp "bütçe sıfır/kritik" gibi
    # yanıltıyordu. reel_butce ay-içi bir bütçe metriği; T+30/T+90 net-değer projeksiyonuna
    # anlamlı oturmaz. (Frontend HorizonsModal bu alanları kullanmıyor — kaldırmak güvenli.)
    kart_kullanim_orani: Optional[float] = None
    delta_vs_baseline: dict = Field(default_factory=dict)


class HorizonsResponse(BaseModel):
    """3-Ufuklu Karar Masasi tam ciktisi."""
    model_config = ConfigDict(protected_namespaces=())

    action_id: int
    ok: bool
    message: str
    baseline: dict = Field(description="Aksiyon olmadan T+max snapshot")
    horizons: list[HorizonSnapshot] = Field(description="T+0, T+30, T+90 sirayla")
    event_log: list[str] = Field(default_factory=list)
    summary: dict = Field(description="30g/90g net deger degisimi karar ozeti")


def _snapshot_to_horizon(snap: dict, label: str, days: int) -> HorizonSnapshot:
    """simulation_engine snapshot dict'inden HorizonSnapshot uretir."""
    return HorizonSnapshot(
        label=label,
        days=days,
        nakit_kasa=float(snap.get("nakit_kasa") or 0.0),
        kart_borcu=float(snap.get("kart_borcu") or 0.0),
        kredi_borcu=float(snap.get("kredi_borcu") or 0.0),
        yatirim_deger=float(snap.get("yatirim_deger") or 0.0),
        net_deger=float(snap.get("net_deger") or 0.0),
        kart_kullanim_orani=snap.get("kart_kullanim_orani"),
        delta_vs_baseline=snap.get("delta_vs_baseline") or {},
    )


@router.post("/{action_id}", response_model=HorizonsResponse)
def simulate_pending_action(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HorizonsResponse:
    """
    Bekleyen aksiyon icin T+0/T+30/T+90 simulasyonu.

    Status pending OLMALI (executed/approved/rejected/failed -> 409).
    Sahiplik kontrolu var (baska kullanicinin aksiyonu -> 404).
    """
    action = db.execute(
        select(PendingAction).where(
            PendingAction.id == action_id,
            PendingAction.user_id == current_user.id,  # scope-exempt: pending lookup (id+user ownership)
        )
    ).scalar_one_or_none()

    if action is None:
        raise HTTPException(status_code=404, detail="Aksiyon bulunamadi")

    if action.status != ActionStatus.pending:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Simulasyon sadece bekleyen aksiyonlar icin calisir. "
                f"Su anki status: {action.status.value}"
            ),
        )

    payload_dict: dict = {}
    if action.payload:
        try:
            payload_dict = json.loads(action.payload)
        except json.JSONDecodeError:
            logger.warning("simulate: payload parse fail action_id=%s", action_id)

    try:
        result = simulate_action(
            db=db,
            user_id=current_user.id,
            action_type=action.action_type,
            payload=payload_dict,
            horizons_days=(0, 30, 90),
        )
    except Exception as e:
        logger.exception("simulate: engine fail action_id=%s", action_id)
        raise HTTPException(
            status_code=500,
            detail=f"Simulasyon motoru hatasi: {e}",
        )

    if not result.get("ok", False):
        logger.warning(
            "simulate: engine ok=False action_id=%s message=%s",
            action_id, result.get("message"),
        )

    label_to_days = {"T+0": 0, "T+30": 30, "T+90": 90}
    horizons: list[HorizonSnapshot] = [
        _snapshot_to_horizon(snap, snap.get("label", "?"),
                             label_to_days.get(snap.get("label", ""), 0))
        for snap in result.get("snapshots", [])
    ]

    logger.info("simulate ok action_id=%s horizons=%d", action_id, len(horizons))

    return HorizonsResponse(
        action_id=action.id,
        ok=bool(result.get("ok", False)),
        message=result.get("message", ""),
        baseline=result.get("baseline") or {},
        horizons=horizons,
        event_log=result.get("event_log") or [],
        summary=result.get("comparison") or {},
    )
