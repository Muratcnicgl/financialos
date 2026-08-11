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

from fastapi import APIRouter, Depends, Request
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
    # BUG #281 (B2): dördüncü tür `kafa_karistirdi` — hata değil, istek de değil:
    # KULLANILABİLİRLİK sinyali ve kapalı betanın en değerli çıktısı. Mevcut üç değer
    # korunur (geçmişe dönük eşleme borcu üretilmez).
    kind: Literal["sikayet", "istek", "oneri", "kafa_karistirdi"]
    message: str = Field(min_length=1, max_length=4000)
    page: Optional[str] = Field(default=None, max_length=80)
    # Kullanıcının ekranda gördüğü korelasyon kimliği (BUG #280). İstemciden gelir ama
    # DOĞRUDAN YAZILMAZ — `correlation.gelen_id_temizle` ile aynı temizleyiciden geçer
    # (L46: kopya değil içe aktarma; ayrıca log/DB'ye enjeksiyon yüzeyi kapanır).
    istek_id: Optional[str] = Field(default=None, max_length=64)
    viewport_w: Optional[int] = Field(default=None, ge=0, le=20000)
    pwa: Optional[bool] = None


class FeedbackOut(BaseModel):
    id: int
    kind: str
    message: str
    page: Optional[str]
    status: str
    created_at: UtcDateTime  # BUG #092: UTC suffix (JS 3 saat kaymasın)
    # Teşhis alanlarından yalnız kullanıcıyı ilgilendiren ikisi geri döner: kendi
    # bildirdiği kod ve hangi sürümde bildirdiği. Tarayıcı/viewport operatör içindir,
    # kullanıcıya geri yansıtmanın bir faydası yok (yüzeyi gereksiz genişletir).
    app_version: Optional[str] = None
    istek_id: Optional[str] = None

    model_config = {"from_attributes": True}


_TARAYICI_DESENLERI = [
    # Sıra ÖNEMLİ: Edge/Opera kendilerini "Chrome" diye de tanıtır, Chrome "Safari" diye.
    # Genelden özele değil, ÖZELDEN GENELE bakılır — aksi halde herkes Safari görünür.
    ("Edg", "Edge"), ("OPR", "Opera"), ("SamsungBrowser", "Samsung"),
    ("Firefox", "Firefox"), ("Chrome", "Chrome"), ("Safari", "Safari"),
]


def tarayici_ailesi(user_agent: Optional[str]) -> Optional[str]:
    """User-Agent'tan kısa aile adı.  # BUG #281 (B2)

    HAM UA **SAKLANMAZ**: sürüm+platform+cihaz üçlüsü güçlü bir parmak izidir ve teşhis
    için gerekmez. Saklanan tek şey "hangi tarayıcı ailesi" — bir hatanın Safari'ye mi
    özgü olduğunu anlamaya yeter, kullanıcıyı tanımlamaya yetmez.
    """
    if not user_agent:
        return None
    for iz, ad in _TARAYICI_DESENLERI:
        if iz in user_agent:
            return ad
    return "diger"


@router.post("", response_model=FeedbackOut, status_code=201)
def create_feedback(
    body: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
) -> FeedbackOut:
    # BUG #281: sürüm İSTEMCİNİN BEYANI DEĞİL, sunucudan türetilir. İstemciye sorulsaydı
    # bayat bir sekme eski sürümü bildirir ve "hangi kod koşuyordu" sorusu yanlış
    # cevaplanırdı — üstelik yanlışlık sessiz olurdu.
    from app.version import full_version
    from app.correlation import gelen_id_temizle

    fb = Feedback(
        user_id=user.id,
        workspace_id=ws_id,
        kind=body.kind,
        message=body.message.strip(),
        page=(body.page or None),
        status="new",
        created_at=datetime.utcnow(),
        app_version=full_version()[:40],
        istek_id=gelen_id_temizle(body.istek_id),
        viewport_w=body.viewport_w,
        tarayici=tarayici_ailesi(request.headers.get("User-Agent")),
        pwa=body.pwa,
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
