"""
FEAT-033 — Uygulama-içi geri bildirim (Şikayet / İstek / Öneri).

Kapalı-beta test-fix döngüsü için basit kanal:
- POST /api/feedback         → yeni geri bildirim gönder
- GET  /api/feedback         → kullanıcının kendi gönderdikleri (newest-first)

kind Pydantic (Literal) ile doğrulanır → DB'de String (dual-dialect basitlik). Workspace-farkında
(scope_filter): kayıt aktif workspace'e bağlanır, listeleme kullanıcının kendi kayıtlarıyla sınırlı.
"""
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id
from app.models import User, Feedback
from app.serializers import UtcDateTime

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

_KIND_LABELS = {"sikayet": "Şikayet", "istek": "İstek", "oneri": "Öneri"}


class FeedbackCreate(BaseModel):
    kind: Literal["sikayet", "istek", "oneri"]
    message: str = Field(min_length=1, max_length=4000)
    page: Optional[str] = Field(default=None, max_length=80)


class FeedbackOut(BaseModel):
    id: int
    kind: str
    message: str
    page: Optional[str]
    status: str
    created_at: UtcDateTime  # BUG #092: UTC suffix (JS 3 saat kaymasın)

    model_config = {"from_attributes": True}


@router.post("", response_model=FeedbackOut, status_code=201)
def create_feedback(
    body: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
) -> FeedbackOut:
    fb = Feedback(
        user_id=user.id,
        workspace_id=ws_id,
        kind=body.kind,
        message=body.message.strip(),
        page=(body.page or None),
        status="new",
        created_at=datetime.utcnow(),
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


@router.get("", response_model=List[FeedbackOut])
def list_feedback(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
) -> List[Feedback]:
    # Kullanıcı yalnız KENDİ gönderdiklerini görür (izolasyon). Admin-tümü görünümü ayrı iş.
    rows = db.execute(
        select(Feedback)
        .where(Feedback.user_id == user.id)
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
    ).scalars().all()
    return rows
