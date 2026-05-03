"""
Coach endpoint'leri (3):
- POST /api/coach/chat       - Mesaj gonder, koc cevabi + bekleyen aksiyonlar
- GET  /api/coach/history    - Sohbet gecmisi
- POST /api/coach/reset      - Gecmisi sifirla (frontend "yeni sohbet" butonu)

WAVE-1 MUKEMMELLESTIRICILER:
1. Her chat cagrisi ApiCallLog'a yaziliyor (Gemini gunluk limit takibi).
2. Su anki gunluk limit kullanim orani GET /api/coach/usage'de geri donuyor.
3. /api/coach/chat cevabinda 'usage' alani var: %80 esigi gectiyse uyari icin.

NOT: app.coach modulu 'CoachEngine' sinifi tutar. Bu router OnA dokunmuyor,
sadece HTTP arayuzu sunar. CoachEngine'in kendi geri yanit + tool routing mantigi
zaten orada calisiyor.

GUNCELLEMELER:
- 2 May 2026 BUG #011 fix: HistoryItem schema artik hem 'timestamp' hem
  'created_at' field'larini doniyor. Frontend Coach.jsx 'created_at' okumaya
  kurulu, sayfa yenilendiginde 'Invalid Date' goruyordu - artik dogru ISO
  string aliyor. 'timestamp' geriye uyumluluk icin korundu.
- 2 May 2026 BUG #013 fix: DB'deki naive UTC timestamp'leri serialize
  edilmeden once timezone-aware UTC'ye ceviriliyor. Boylece JSON cikti
  '+00:00' suffix'iyle gidiyor, frontend artik 3 saat geri gostermiyor.
"""

import time
import logging
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.dependencies import get_db, get_current_user
from app.models import User, CoachMemory, ApiCallLog, ApiCallStatus
from app.coach import CoachEngine

router = APIRouter(prefix="/api/coach", tags=["coach"])

logger = logging.getLogger(__name__)


# ============================================================
# SCHEMAS
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    include_cockpit: bool = Field(True, description="System prompt'a Cockpit ekle (default True)")


class ProposedActionOut(BaseModel):
    action_id: int
    action_type: str
    summary: str
    payload: Dict[str, Any]


class UsageInfo(BaseModel):
    """Gunluk LLM cagri sayilari ve uyarilar."""
    today_count: int
    daily_limit: int
    percentage: float
    warn: bool                 # %80 ustunde mi?
    block: bool                # %100 mi?


class ChatResponse(BaseModel):
    reply: str
    proposed_actions: List[ProposedActionOut]
    cockpit_snapshot: Optional[Dict[str, Any]] = None
    usage: Optional[UsageInfo] = None


class HistoryItem(BaseModel):
    """
    Sohbet gecmis kaydi.

    BUG #011 fix: Frontend 'created_at' field adiyla okuyor, backend eskiden
    'timestamp' donuyordu, bu yuzden Invalid Date hatasi vardi. Simdi her ikisi
    de doniyor — frontend hangisini okursa okusun calisir.
    """
    id: int
    role: str
    content: str
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ResetResponse(BaseModel):
    deleted: int


# ============================================================
# YARDIMCILAR
# ============================================================

# Gemini ucretsiz limit (1500 ist/gun). Provider degisirse ileride dinamik yapariz.
GEMINI_DAILY_LIMIT = 1500


def _today_call_count(db: Session, user_id: int, provider: str) -> int:
    today_start = datetime.combine(date.today(), datetime.min.time())
    return (
        db.query(func.count(ApiCallLog.id))
        .filter(
            ApiCallLog.user_id == user_id,
            ApiCallLog.provider == provider,
            ApiCallLog.called_at >= today_start,
        )
        .scalar() or 0
    )


def _build_usage_info(db: Session, user_id: int, provider: str) -> UsageInfo:
    count = _today_call_count(db, user_id, provider)
    pct = round((count / GEMINI_DAILY_LIMIT) * 100, 1) if provider == "gemini" else 0.0
    return UsageInfo(
        today_count=count,
        daily_limit=GEMINI_DAILY_LIMIT if provider == "gemini" else 999999,
        percentage=pct,
        warn=pct >= 80.0,
        block=pct >= 100.0,
    )


def _log_api_call(
    db: Session,
    user_id: int,
    provider: str,
    model: str,
    success: bool,
    duration_ms: int,
    tool_calls_count: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """ApiCallLog'a tek satir yazar. Hata icinde basarisiz olsa bile chat'i kirletmez."""
    try:
        log = ApiCallLog(
            user_id=user_id,
            provider=provider.lower(),
            model=model,
            status=ApiCallStatus.success if success else ApiCallStatus.failed,
            tool_calls_count=tool_calls_count,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning(f"ApiCallLog yazimi basarisiz: {e}")
        db.rollback()


def _memory_to_history_item(m: CoachMemory) -> HistoryItem:
    """
    BUG #011 fix: CoachMemory.timestamp'i hem timestamp hem created_at field'i
    olarak donduruyoruz. CoachMemory modelinde sadece 'timestamp' var ama frontend
    'created_at' bekliyor.

    BUG #013 fix: DB'deki timestamp 'datetime.utcnow()' ile yazildigi icin
    timezone-naive UTC. Suffix'siz serialize edildiginde frontend bunu LOCAL
    olarak yorumluyor ve 3 saat geri gosteriyordu. Burada naive degeri aware
    UTC'ye cevirip Pydantic'in '+00:00' suffix'i ile yayinlamasini sagliyoruz.
    """
    ts = m.timestamp
    if ts is not None and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return HistoryItem(
        id=m.id,
        role=m.role,
        content=m.content,
        timestamp=ts,
        created_at=ts,
    )


# Tek paylasilan CoachEngine instance — provider client'i her cagri icin
# yeniden olusturmak yerine baglantiyi tekrar kullanir.
_engine: Optional[CoachEngine] = None


def _get_engine() -> CoachEngine:
    global _engine
    if _engine is None:
        _engine = CoachEngine()
    return _engine


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    """
    Koc'a mesaj gonder.

    Cevap:
    - reply: Koc'un metin cevabi (rapor veya kisa bilgi)
    - proposed_actions: Koc bir aksiyon onerdiyse (sattim/odedim/aldim) burada gelir
    - cockpit_snapshot: O an alinan cockpit snapshot'i (frontend zaten yine /api/cockpit
      cagirsa da bunun anlik kopyasi audit icin kullanisli)
    - usage: Gunluk Gemini limit kullanim orani (rate limit uyarisi icin)
    """
    engine = _get_engine()
    provider_name = engine.provider_name.replace("Provider", "").lower()  # 'gemini' veya 'anthropic'
    model = engine.model

    # Pre-check: gunluk limit dolmussa cevap vermeden once uyar
    pre_usage = _build_usage_info(db, user.id, provider_name)
    if pre_usage.block:
        raise HTTPException(
            status_code=429,
            detail=f"Gunluk LLM limiti doldu ({pre_usage.today_count}/{pre_usage.daily_limit}). "
                   f"Yarin sifirlanacak. Anthropic'e gecis icin .env: LLM_PROVIDER=anthropic.",
        )

    # Asil cagri + sure olcumu
    t_start = time.time()
    success = True
    error_msg = None
    tool_calls_count = 0

    try:
        result = engine.chat(
            db=db,
            user_id=user.id,
            user_message=payload.message,
            include_cockpit=payload.include_cockpit,
        )
        tool_calls_count = len(result.get("proposed_actions") or [])
    except Exception as e:
        success = False
        error_msg = str(e)
        result = {
            "reply": f"Koc cevap veremedi: {e}",
            "proposed_actions": [],
            "cockpit_snapshot": None,
        }

    duration_ms = int((time.time() - t_start) * 1000)
    _log_api_call(
        db, user.id, provider_name, model,
        success=success, duration_ms=duration_ms,
        tool_calls_count=tool_calls_count, error_message=error_msg,
    )

    # Post-call usage (yeni log dahil)
    post_usage = _build_usage_info(db, user.id, provider_name)

    return ChatResponse(
        reply=result["reply"],
        proposed_actions=[
            ProposedActionOut(**pa) for pa in (result.get("proposed_actions") or [])
        ],
        cockpit_snapshot=result.get("cockpit_snapshot"),
        usage=post_usage,
    )


@router.get("/history", response_model=List[HistoryItem])
def get_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[HistoryItem]:
    """
    Sohbet gecmisi. Default son 50 mesaj, kronolojik (eski->yeni).
    Frontend chat panel'i bunu yukler.

    BUG #011 fix: Her item hem 'timestamp' hem 'created_at' iceriyor.
    """
    items = (
        db.query(CoachMemory)
        .filter(CoachMemory.user_id == user.id)
        .order_by(CoachMemory.timestamp.desc())
        .limit(limit)
        .all()
    )
    items.reverse()
    return [_memory_to_history_item(m) for m in items]


@router.post("/reset", response_model=ResetResponse)
def reset_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResetResponse:
    """
    Sohbet gecmisini tamamen sifirla. Kullanici 'yeni sohbet' demek istediginde.
    NOT: Bu islem geri alinamaz. Frontend'de 'eminmisin?' onayi olmali.
    """
    engine = _get_engine()
    deleted = engine.reset_history(db, user.id)
    return ResetResponse(deleted=deleted)


@router.get("/usage", response_model=UsageInfo)
def get_usage(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UsageInfo:
    """
    Bugunku LLM cagri sayisi + limit yuzdesi. Cockpit panel'i ust kosesinde
    'API kullanim: %42' rozetini bundan cekecek.
    """
    engine = _get_engine()
    provider_name = engine.provider_name.replace("Provider", "").lower()
    return _build_usage_info(db, user.id, provider_name)