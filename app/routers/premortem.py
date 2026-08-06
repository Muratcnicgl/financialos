"""
POST /api/premortem/{action_id}

Bekleyen bir aksiyon icin Klein (1989) premortem analizi uretir ve
DecisionJournal'a kaydeder. LLM cagrisi senkron — kullanici UI'da bekler.

GUNCELLEMELER:
- BUG #224 fix (D03b): uc workspace baglamini hic kurmuyordu → `build_cockpit_snapshot`
  (generate_cockpit) aile workspace'i seciliyken KISISEL manzarayi uretiyor, LLM'e
  yanlis baglam gidiyordu. Uyelik dogrulamasi da yoktu.
- BUG #228 fix (D07): uc LLM KOTASINI TAMAMEN ATLIYORDU. Kotasi dolmus (429 almis)
  bir kullanici bile bu ucu donguye sokup sinirsiz uretim yaptirabiliyordu; uretim
  ApiCallLog'a hic yazilmadigi icin maliyet/hata metrikleri bu trafigi gormuyordu.
  Artik paylasilan `app/llm_quota` uzerinden rezerve edilir. Onbellekten donen istek
  rezervasyonu iptal eder (yapilmamis cagri icin kullanici cezalandirilmaz).
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cockpit_snapshot import build_cockpit_snapshot, compute_snapshot_hash
from app.dependencies import get_db, get_current_user
from app.scope import workspace_scope  # BUG #224: aktif workspace kapsami
from app import llm_quota as _kota  # BUG #228: LLM kotasi (tek kaynak)
from app.workspace_deps import active_workspace_id  # BUG #224: uyelik dogrulama + ws cozumu
from app.models import ActionStatus, PendingAction, User
from app.premortem import (
    PremortemError,
    PremortemScenario,
    generate_premortem,
    persist_premortem,
    load_cached_premortem,  # BUG #137 (P1-22): cockpit değişmediyse LLM'siz cache dönüşü
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
    ws_id: Optional[int] = Depends(active_workspace_id),  # BUG #224
):
    """
    Bekleyen aksiyon icin 3-5 basarisizlik senaryosu uretir (Klein premortem).
    Sonuc DecisionJournal'a yazilir ve dogrudan doner.
    Sadece status=pending aksiyonlar kabul edilir.
    Kapsam: aktif workspace (X-Workspace-Id; yoksa personal). BUG #224.
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

    with workspace_scope(ws_id):  # BUG #224: cockpit ile ayni kapsam kaynagi
        snapshot = build_cockpit_snapshot(db, current_user.id)
    snapshot_hash = compute_snapshot_hash(snapshot)

    # BUG #137 (P1-22): aynı cockpit_snapshot_hash için önceden üretilmiş premortem varsa
    # LLM'i tekrar çağırma — cache'ten dön (cockpit değişmemiş = senaryolar geçerli).
    cached = load_cached_premortem(db, action, current_user.id, snapshot_hash)
    if cached:
        dj_id, scenarios = cached
        return PremortemResponse(
            action_id=action.id,
            scenarios=scenarios,
            provider_used="cache",
            model_name=None,
            persisted_decision_journal_id=dj_id,
            cached=True,
        )

    # BUG #228 (D07): kota ÇAĞRI ÖNCESİ rezerve edilir (önbellek dalından SONRA — cache
    # LLM harcamaz). Tavan doluysa 429; koç sohbetiyle aynı kural, aynı sayaç.
    rezervasyon = _kota.rezerve_et(db, current_user.id, provider="premortem",
                                   model="premortem")
    # BUG #234 (D15, sınıf taraması): tek rezervasyon satırı yalnız BİR gerçek isteği
    # karşılar; zincir/retry birden fazla istek üretirse fark uzlaştırılır.
    olcum: dict = {}
    try:
        with _kota.cagri_olcumu() as olcum:
            result = generate_premortem(
                action_id=action.id,
                action_context=action_context,
                cockpit_snapshot=snapshot,
            )
    except PremortemError as e:
        # Çöken çağrı da sayılır (sağlayıcıya gitti) — koç yolundaki davranışla aynı.
        _kota.tamamla(db, rezervasyon, success=False, error_message=str(e))
        _kota.ek_cagrilari_uzlastir(db, current_user.id, olcum, rezervasyon, "premortem")
        logger.error("premortem generation failed action_id=%s error=%s", action_id, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Premortem su anda cevap veremedi. Lutfen tekrar deneyin.",  # BUG #175
        )
    _kota.tamamla(db, rezervasyon, provider=result.provider_used, success=True)
    _kota.ek_cagrilari_uzlastir(db, current_user.id, olcum, rezervasyon, "premortem")

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
