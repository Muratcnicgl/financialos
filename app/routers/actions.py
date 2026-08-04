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

import json
import logging
import os
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.serializers import UtcDateTime  # BUG #092: datetime UTC suffix
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import (
    User, PendingAction, ActionStatus, ActionHistory, ActionSource,
)
from app.action_executor import (
    execute_pending_action, reject_pending_action, _normalize_transaction_payload,
)
from app.premortem import link_premortem_outcome
from app.rules_engine import generate_cockpit, workspace_scope  # M43
from app.workspace_deps import active_workspace_id, require_write  # M43, require_write

router = APIRouter(prefix="/api/actions", tags=["actions"], dependencies=[Depends(require_write())])

logger = logging.getLogger(__name__)

# Reflection: sadece Groq, 8B önce 70B fallback, başka provider yok
_REFLECTION_MODELS = os.getenv(
    "REFLECTION_MODELS", "llama-3.1-8b-instant,llama-3.3-70b-versatile"
).split(",")
_REFLECTION_AMOUNT_THRESHOLD = 100.0
_REFLECTION_ACTION_TYPES = {"add_transaction", "sell_investment", "mark_debt_paid"}


def _should_reflect(action_type: str, payload: dict) -> bool:
    """Reflection atlanacak durumlar: güncelleme tipi, gelir, 100 TL altı harcama."""
    if action_type not in _REFLECTION_ACTION_TYPES:
        return False
    if action_type == "add_transaction":
        if payload.get("transaction_type") == "income":
            return False
        if float(payload.get("amount", 0)) < _REFLECTION_AMOUNT_THRESHOLD:
            return False
    return True


def _run_reflection(user_id: int, action_type: str, summary: str, payload_str: str) -> None:
    """
    Background task: onaylanan aksiyonu hafızayla değerlendir.

    Neden router'da (action_executor'da değil):
    execute_pending_action zaten commit edilmiş → rollback güvenliği:
    reflection patlarsa aksiyon geri alınmaz, kullanıcıya yansımaz.
    BackgroundTasks FastAPI'da router-native; executor'da async yok.

    Sadece Groq: 8B→70B fallback. Gemini/Anthropic quota korunur.
    Her hata sessiz fail — logger'a yazılır, kullanıcıya gösterilmez.
    """
    from app.database import SessionLocal
    from app.models import CoachInsight
    from app.coach import save_insight_action, SAVE_INSIGHT_SCHEMA, GroqProvider

    db = None
    try:
        db = SessionLocal()
        payload = json.loads(payload_str) if payload_str else {}
        amount = payload.get("amount", 0)
        category = payload.get("category", "")

        # Mevcut dedup_key'ler: virgülle ayrılmış tek satır (token tasarrufu)
        rows = (
            db.query(CoachInsight.dedup_key)
            .filter(
                CoachInsight.user_id == user_id,
                CoachInsight.is_active == True,
                CoachInsight.dedup_key != None,
            )
            .order_by(CoachInsight.priority.desc(), CoachInsight.created_at.desc())
            .limit(20)
            .all()
        )
        existing_keys = ", ".join(r[0] for r in rows if r[0]) or "(henüz yok)"

        system_prompt = (
            "Sen FinancialOS hafıza yazıcısısın. Onaylanan aksiyonu analiz et.\n"
            "Kalıcı öğrenilebilecek bir şey (harcama kalıbı, tercih, beklenmedik maliyet) varsa "
            "save_insight çağır. Yoksa hiçbir şey yapma — boş cevap kabul edilir.\n\n"
            f"# Onaylanan Aksiyon\n"
            f"Tür: {action_type} | Özet: {summary} | Tutar: {amount} TL | Kategori: {category}\n\n"
            f"# Mevcut dedup_key'ler (bunları tekrarlama; uygunsa kullan)\n"
            f"{existing_keys}\n\n"
            "# dedup_key kuralı\n"
            "snake_case, konu+hesap/kategori+frekans özetle. "
            "Örnek: market_expense_weekly / fuel_cash_pattern / ziraat_preference_expense"
        )

        groq_key = os.getenv("GROQ_API_KEY", "")
        if not groq_key:
            logger.warning("reflection: GROQ_API_KEY eksik, atlanıyor")
            return

        last_exc = None
        for model in _REFLECTION_MODELS:
            try:
                provider = GroqProvider(api_key=groq_key, model=model.strip())
                response = provider.chat(
                    system_prompt=system_prompt,
                    messages=[{"role": "user", "content": "Analiz et."}],
                    tools=[SAVE_INSIGHT_SCHEMA],
                )
                for tc in response.tool_calls:
                    if tc["name"] == "save_insight":
                        inp = tc["input"]
                        result = save_insight_action(
                            db=db,
                            user_id=user_id,
                            content=inp["content"],
                            category=inp.get("category", "pattern"),
                            priority=inp.get("priority", "normal"),
                            dedup_key=inp.get("dedup_key", ""),
                            expires_at=inp.get("expires_at"),
                        )
                        logger.info(
                            f"reflection insight [{result.dedup_key}]: {result.content[:60]}"
                        )
                return  # başarılı
            except Exception as e:
                last_exc = e
                logger.warning(f"reflection model {model} hata: {e}")
                continue

        if last_exc:
            logger.warning(f"reflection sessiz fail (tüm modeller denendi): {last_exc}")

    except Exception as e:
        logger.warning(f"reflection sessiz fail: {e}")
    finally:
        if db:
            db.close()


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
    created_at: UtcDateTime
    resolved_at: Optional[UtcDateTime] = None

    model_config = {"from_attributes": True}


class RejectRequest(BaseModel):
    reason: Optional[str] = None


class EditActionRequest(BaseModel):
    payload: dict
    summary: str


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
    applied_at: UtcDateTime

    model_config = {"from_attributes": True}


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/pending", response_model=List[PendingActionOut])
def get_pending_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """Onay bekleyen tum aksiyonlari listele (aktif workspace)."""
    from app.workspace_deps import scope_filter
    actions = (
        db.query(PendingAction)
        .filter(
            scope_filter(PendingAction, current_user.id, ws_id),  # M43
            PendingAction.status == ActionStatus.pending,
        )
        .order_by(PendingAction.created_at.desc())
        .all()
    )
    return actions


@router.post("/{action_id}/approve")
def approve_action(
    action_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """Aksiyonu onayla ve uygula. ActionHistory'e snapshot yaz.
    Reflection hook router'da tetiklenir — execute commit sonrası,
    reflection hatası aksiyonu etkilemez (rollback güvenliği)."""
    from datetime import date

    # Oncelik: net worth snapshot al (execute oncesi) — M43: aktif workspace deltası
    with workspace_scope(ws_id):
        cockpit_before = generate_cockpit(current_user.id, date.today(), db)
    net_worth_before = cockpit_before.get("net_deger")
    cash_before = cockpit_before.get("nakit_kasa")

    # Pending action'i bul (execute icin)
    pending = (
        db.query(PendingAction)
        .filter(
            PendingAction.id == action_id,
            PendingAction.user_id == current_user.id,  # scope-exempt: pending ownership (id+user, personal-bound)
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

    # Execute sonrasi snapshot — M43: aktif workspace deltası
    with workspace_scope(ws_id):
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

    # Premortem outcome linki — premortem cagirilmamissa sessiz gec (None doner)
    # BUG #131 fix (P1-23): aksiyon ZATEN executed+committed (yukarida). Bu post-commit cagri
    # firlatirsa basarili aksiyon kullaniciya 500 doner (response/gercek-durum celiskisi).
    # Reflection hook (asagida) gibi try/except ile sar — hatada logla, response'u etkileme.
    try:
        link_premortem_outcome(
            session=db,
            pending_action_id=pending.id,
            action_history_id=history_entry.id,
            success=result.get("success", False),
            message=result.get("message", ""),
        )  # BUG #138 (P1-19): net_worth_delta ölü paramdı, kaldırıldı
    except Exception as e:
        logger.warning(f"premortem outcome link basarisiz (sessiz, aksiyon zaten executed): {e}")

    # Reflection hook: commit sonrası background — rollback güvenliği garanti
    try:
        payload_dict = json.loads(pending.payload) if pending.payload else {}
        if _should_reflect(pending.action_type, payload_dict):
            background_tasks.add_task(
                _run_reflection,
                user_id=current_user.id,
                action_type=pending.action_type,
                summary=pending.summary,
                payload_str=pending.payload,
            )
    except Exception as e:
        logger.warning(f"reflection task eklenemedi (sessiz): {e}")

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


@router.post("/{action_id}/edit", response_model=PendingActionOut)
def edit_action(
    action_id: int,
    body: EditActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pending aksiyonun payload ve summary'sini guncelle (kullanici duzeltmesi)."""
    pending = (
        db.query(PendingAction)
        .filter(
            PendingAction.id == action_id,
            PendingAction.user_id == current_user.id,  # scope-exempt: pending ownership (id+user, personal-bound)
            PendingAction.status == ActionStatus.pending,
        )
        .first()
    )
    if not pending:
        raise HTTPException(status_code=404, detail="Aksiyon bulunamadi veya artik duzenlenemez.")

    new_payload = body.payload
    # add_transaction icin kart normalizasyonunu yeniden calistir
    if pending.action_type == "add_transaction":
        try:
            new_payload = _normalize_transaction_payload(new_payload, current_user.id, db)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Aksiyon icerigi gecersiz.")  # BUG #175

    pending.payload = json.dumps(new_payload, ensure_ascii=False, default=float)
    pending.summary = body.summary
    db.commit()
    db.refresh(pending)
    return pending


@router.get("/history", response_model=List[ActionHistoryOut])
def get_action_history(
    limit: int = Query(50, ge=1, le=500),  # BUG #154 (P2-5): ust sinir
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









