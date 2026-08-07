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
- 4 May 2026 BUG #040 fix: _memory_to_history_item role='tool' satirlarini
  None donduruyor (frontend'e gonderilmez). role='assistant' + content bos +
  tool_calls_json dolu ise placeholder set ediliyor. get_history None filtreliyor.
- 5 Agu 2026 BUG #212 fix (H17, eszamanlilik): kota sayaci artik cagri ONCESI
  rezerve ediliyor (_kota_rezerve_et / _rezervasyonu_tamamla) — "oku -> cagir ->
  yaz" akisinda paralel istekler ayni eski sayiyi okuyup tavani deliyordu.
  Ayrica muhasebe etiketi FallbackProvider'in PAYLASILAN last_used_provider
  alanindan degil yapilandirmadan turetiliyor (_muhasebe_saglayici_adi) — eski
  etiket "fallback(gemini)" PROVIDER_DAILY_LIMITS'te olmadigi icin gunluk kota
  korumasi sessizce oluyordu.
"""

import os
import json
import time
import logging
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.serializers import UtcDateTime  # BUG #092: datetime UTC suffix
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id  # M43
from app.rules_engine import workspace_scope  # M43
from app.models import User, CoachMemory, ApiCallLog, ApiCallStatus, PendingAction, ActionStatus, ReasoningTrace
from app.coach import CoachEngine
from app import llm_quota as _kota  # BUG #228: kota muhasebesinin tek kaynağı
from app import capacity as kapasite  # BUG #263 (P5.5): eşzamanlı LLM tavanı

router = APIRouter(prefix="/api/coach", tags=["coach"])

logger = logging.getLogger(__name__)


# ============================================================
# SCHEMAS
# ============================================================

class ChatRequest(BaseModel):
    # SEC-006: üst sınır — sınırsız girdi sağlayıcı token limitini aşar (413), maliyet/bellek
    # riski. 4000 karakter finansal olay tarifi için fazlasıyla yeterli; aşarsa 422 (net hata).
    message: str = Field(..., min_length=1, max_length=4000)
    include_cockpit: bool = Field(True, description="System prompt'a Cockpit ekle (default True)")


class ProposedActionOut(BaseModel):
    action_id: int
    action_type: str
    summary: str
    payload: Dict[str, Any]


class UsageInfo(BaseModel):
    """Gunluk LLM cagri sayilari ve uyarilar.

    BUG #234 (D14): `today_count` PAYLASILAN saglayici sayacidir — anahtari kullanan
    HERKESIN bugunku gercek istekleri. Eskiden kullanici-basina filtreliydi, yani
    sozlesmenin (asagidaki yorum) soyledigi seyi hic olcmuyordu.
    """
    today_count: int
    daily_limit: int
    percentage: float
    warn: bool                 # %80 ustunde mi? (operator gorunurlugu — her modda)
    block: bool                # tavan doldu VE alternatif saglayici yok → istek reddedilir
    # BUG #188 (P3): KULLANICI-BASINA tavan. Yukaridakiler saglayicinin PAYLASILAN gunluk
    # kotasidir; tek kullanici onu tuketirse herkes kilitlenir. Bu iki alan kisisel tavandir.
    user_today_count: int = 0
    user_daily_limit: int = 0


class ChatResponse(BaseModel):
    reply: str
    proposed_actions: List[ProposedActionOut]
    cockpit_snapshot: Optional[Dict[str, Any]] = None
    usage: Optional[UsageInfo] = None
    coach_memory_id: Optional[int] = None


class TraceStepOut(BaseModel):
    """Single ReasoningTrace step serialized for the trace panel."""

    id: int
    step_index: int
    parent_step_id: Optional[int] = None
    operation_name: str
    intent: Optional[str] = None
    action_input_json: Optional[str] = None
    observation: Optional[str] = None
    inference: Optional[str] = None
    confidence_score: Optional[float] = None
    provider_system: Optional[str] = None
    model_name: Optional[str] = None
    usage_input_tokens: Optional[int] = None
    usage_output_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: UtcDateTime

    # BUG #118: model_name alanı Pydantic'in korumalı "model_" namespace'iyle çakışıyor →
    # protected_namespaces=() ile uyarı susturulur (alan API sözleşmesi, yeniden adlandırılmaz).
    model_config = {"from_attributes": True, "protected_namespaces": ()}


class TraceResponse(BaseModel):
    """Top-level response for GET /api/coach/trace/{memory_id}."""

    coach_memory_id: int
    trace_id: str
    steps: List[TraceStepOut]


class ActionDTO(BaseModel):
    """BUG #046 fix: History'de inline gosterilecek pending aksiyon ozeti."""
    id: int
    action_type: str
    summary: str
    payload: str          # JSON string (frontend parse eder)
    warning: Optional[str] = None
    status: ActionStatus

    model_config = {"from_attributes": True}


class HistoryItem(BaseModel):
    """
    Sohbet gecmis kaydi.

    BUG #011 fix: Frontend 'created_at' field adiyla okuyor, backend eskiden
    'timestamp' donuyordu, bu yuzden Invalid Date hatasi vardi. Simdi her ikisi
    de doniyor — frontend hangisini okursa okusun calisir.
    BUG #046 fix: actions field eklendi — history yuklendiginde kart gorunur.
    """
    id: int
    role: str
    content: str
    timestamp: UtcDateTime
    created_at: UtcDateTime
    actions: List[ActionDTO] = []  # BUG #046: pending aksiyonlar (history reload)

    # BUG #118 fix: Pydantic V2 stili (app/PROJE.md kuralı — V1 `class Config` deprecated).
    model_config = {"from_attributes": True}


class ResetResponse(BaseModel):
    deleted: int


# ============================================================
# YARDIMCILAR
# ============================================================

# BE-025: Sağlayıcı GÜNLÜK çağrı limitleri (ücretsiz kademe). Gemini günlük 1500 ist/gün.
# Groq/Cerebras TPM (dakika-başı token) limitli — GÜNLÜK limit yok → % anlamsız (None).
GEMINI_DAILY_LIMIT = 1500
PROVIDER_DAILY_LIMITS = {"gemini": GEMINI_DAILY_LIMIT}


def _daily_constrained_provider(provider: str) -> str:
    """
    BE-025: Günlük-kota bakımından raporlanacak FİİLİ kısıtlayıcı sağlayıcı. `fallback`
    modda circuit breaker gpt-oss'u (Groq/Cerebras, TPM) eleyince fiili birincil Gemini olur
    → günlük kota onun. Bu yüzden fallback/gemini → 'gemini' raporlanır (eskiden 'fallback'
    için hep %0 dönüyordu → günlük-limit koruması FALLBACK'te ÖLÜYDÜ). Diğer sağlayıcılar kendisi.
    """
    return "gemini" if provider in ("fallback", "gemini") else provider


def _muhasebe_saglayici_adi(engine: CoachEngine) -> str:
    """BUG #212 (H17): kota muhasebesi için KARARLI sağlayıcı adı.

    Eskiden `engine.provider_name` kullanılıyordu; o property FallbackProvider'ın
    **paylaşılan** `last_used_provider` alanını okur ve ilk başarılı çağrıdan sonra
    "Fallback(Gemini)" döner → `fallback(gemini)` etiketi PROVIDER_DAILY_LIMITS'te
    yoktur → `limit=None` → **günlük kota koruması sessizce ÖLÜR** (block hiç true
    olmaz). Üstelik alan paylaşıldığı için etiket, eşzamanlı BAŞKA bir kullanıcının
    çağrısına göre değişir: aynı istek bazen "fallback", bazen "fallback(gemini)"
    muhasebeleşir. Etiket artık yapılandırmadan türetilir, çalışma-anı durumundan değil.
    """
    from app.coach import FallbackProvider
    provider = getattr(engine, "provider", None)
    if provider is None:   # test ikizleri / özel motorlar: eski yola düş
        return str(getattr(engine, "provider_name", "?")).replace("Provider", "").lower()
    if isinstance(provider, FallbackProvider):
        return "fallback"
    return str(getattr(provider, "NAME", type(provider).__name__)).replace("Provider", "").lower()


def _today_call_count(db: Session, user_id: int, provider: str) -> int:
    """Saglayicinin bugunku PAYLASILAN cagri sayisi (BUG #234 / D14).

    `user_id` yalnizca geriye-uyum icin imzada durur — saglayici kotasi tek havuzdur,
    kullanici basina filtrelenirse hic olculmez (govde: app/llm_quota).

    BUG #133 (P1-7): sayac UTC gunune gore — `called_at` ile ayni zaman ekseni. Sunucu
    yerel gunu kullanilirsa TR'de (UTC+3) sayac 3 saat erken sifirlanir.
    """
    return _kota.paylasilan_cagri_sayisi(db, provider)


# BUG #228 (D07/D16): kota muhasebesi bu router'dan SÖKÜLDÜ → `app/llm_quota.py`.
# Kota uca değil LLM KULLANIMINA bağlıdır; premortem ve aksiyon-yansıması gibi diğer
# yollar aynı kaynaktan geçer (aksi halde tavan o yollardan sıfırlanıyordu).
# Buradaki isimler geriye-uyum sarmalayıcısıdır.
coach_user_daily_limit = _kota.kullanici_gunluk_tavan
_user_today_call_count = _kota.bugunku_cagri_sayisi


def _alternatif_saglayici_var(engine: CoachEngine) -> bool:
    """BUG #234 (D14 + L6): zincirde YEDEK sağlayıcı var mı?

    Paylaşılan günlük tavan dolduğunda isteği reddetmek yalnız alternatifi olmayan
    (tek-sağlayıcı) kurulumda doğrudur. Fallback zincirinde birincil 429 alınca
    `FallbackProvider` bir sonraki sağlayıcıya geçer — ürün ÇALIŞIYORken uygulamanın
    kendisini kilitlemesi gereksiz kesinti olur. Bu modda tavan yalnız `warn` ile
    operatöre raporlanır.
    """
    from app.coach import FallbackProvider
    provider = getattr(engine, "provider", None)
    return isinstance(provider, FallbackProvider) and len(getattr(provider, "providers", [])) > 1


def _build_usage_info(db: Session, user_id: int, provider: str,
                      alternatif_var: bool = False) -> UsageInfo:
    """BUG #234 (D14): `block` = "istek REDDEDİLECEK".

    Yedekli zincirde paylaşılan tavan dolsa bile istek reddedilmez (bir sonraki sağlayıcı
    devralır) → `block` False kalır, aksi halde arayüz çalışan ürünü kilitler (ölü UI'ın
    tersi: yanlış-pozitif kilit). `warn` her modda ateşler — operatör tükenmeyi görsün.
    """
    target = _daily_constrained_provider(provider)
    count = _today_call_count(db, user_id, target)
    limit = PROVIDER_DAILY_LIMITS.get(target)
    if not limit:
        # günlük limiti bilinmeyen sağlayıcı (TPM-limitli) → sayıyı göster, % yanıltmasın
        return UsageInfo(today_count=count, daily_limit=0, percentage=0.0, warn=False, block=False,
                         user_today_count=_user_today_call_count(db, user_id),
                         user_daily_limit=coach_user_daily_limit())
    pct = round((count / limit) * 100, 1)
    return UsageInfo(
        today_count=count,
        daily_limit=limit,
        percentage=pct,
        warn=pct >= 80.0,
        block=pct >= 100.0 and not alternatif_var,
        user_today_count=_user_today_call_count(db, user_id),
        user_daily_limit=coach_user_daily_limit(),
    )


def _kota_rezerve_et(db: Session, user_id: int, provider: str, model: str,
                     kisisel_tavan: int) -> ApiCallLog:
    """BUG #212 (H17): çağrı ÖNCESİ sayaç satırı yaz — eşzamanlı istekler tavanı delmesin.

    BUG #228 (D07/D16): gövde `app/llm_quota.rezerve_et`'e taşındı (tek kaynak); bu
    sarmalayıcı çağıranları ve mevcut testleri kırmadan aynı sözleşmeyi sürdürür.
    """
    return _kota.rezerve_et(db, user_id, provider, model, tavan=kisisel_tavan)


def _rezervasyonu_tamamla(db: Session, log: ApiCallLog, provider: str, success: bool,
                          duration_ms: int, tool_calls_count: int,
                          error_message: Optional[str]) -> None:
    """Rezerve edilen satırı çağrı sonucuyla günceller (BUG #212, gövde: app/llm_quota)."""
    _kota.tamamla(db, log, provider=provider, success=success, duration_ms=duration_ms,
                  tool_calls_count=tool_calls_count, error_message=error_message)


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
        # SEC-009: ham sağlayıcı hatası (kota/org detayı içerebilir) 300 karakterle sınırlanır —
        # DB/export şişmesin + gereksiz detay birikmesin (api_call_log artık KVKK export'unda).
        log = ApiCallLog(
            user_id=user_id,
            provider=provider.lower(),
            model=model,
            status=ApiCallStatus.success if success else ApiCallStatus.failed,
            tool_calls_count=tool_calls_count,
            duration_ms=duration_ms,
            error_message=(error_message[:300] if error_message else None),
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning(f"ApiCallLog yazimi basarisiz: {e}")
        db.rollback()


def _memory_to_history_item(m: CoachMemory, pa_map: Dict[int, PendingAction] = None) -> Optional[HistoryItem]:
    """
    BUG #011/#013/#040/#046 fix: CoachMemory kaydini HistoryItem'e cevir.
    pa_map: pending action ID -> PendingAction; batch lookup icin get_history tarafindan verilir.
    """
    if m.role == 'tool':  # BUG #040: tool satırları frontend'e gönderilmez
        return None

    content = m.content
    if m.role == 'assistant' and not content and m.tool_calls_json:  # BUG #040
        content = "Onayınız için bir aksiyon hazırladım. Detayı aşağıdaki kartta görebilirsin."

    ts = m.timestamp
    if ts is not None and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    # BUG #046: pending aksiyon kartlarini history'ye dahil et
    actions: List[ActionDTO] = []
    if pa_map and m.pending_action_ids_json:
        try:
            ids = json.loads(m.pending_action_ids_json)
            for aid in ids:
                pa = pa_map.get(aid)
                if pa:
                    actions.append(ActionDTO.model_validate(pa))
        except Exception:
            # BE-010: bozuk pending_action_ids_json veya DTO doğrulama hatası → kart atlanır
            # ama loglanır (history'de aksiyon sessizce kaybolmasın).
            logger.warning("history pending aksiyon kartı oluşturulamadı memory=%s",
                           getattr(m, "id", "?"), exc_info=True)

    return HistoryItem(
        id=m.id,
        role=m.role,
        content=content,
        timestamp=ts,
        created_at=ts,
        actions=actions,
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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
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
    # BUG #212 (H17): muhasebe etiketi PAYLASILAN calisma-ani durumundan degil,
    # yapilandirmadan turetilir (bkz. _muhasebe_saglayici_adi).
    provider_name = _muhasebe_saglayici_adi(engine)
    model = engine.model

    # Pre-check: gunluk limit dolmussa cevap vermeden once uyar
    yedek_var = _alternatif_saglayici_var(engine)
    pre_usage = _build_usage_info(db, user.id, provider_name, alternatif_var=yedek_var)
    # BUG #188 (P3): KULLANICI-BASINA tavan — saglayici kotasindan BAGIMSIZ. Paylasilan
    # kotayi tek kisi tuketip digerlerini kilitleyemez; maliyet de kullanici basina sinirli.
    kisisel_tavan = coach_user_daily_limit()
    if kisisel_tavan and pre_usage.user_today_count >= kisisel_tavan:
        raise HTTPException(
            status_code=429,
            detail="Bugunku koc kullanim hakkin doldu. Yarin yeniden sohbet edebilirsin — "
                   "paneller ve hesaplamalar calismaya devam ediyor.",
        )
    # BUG #234 (D14): bu dal artik GERCEKTEN erisilebilir (paylasilan sayac olculuyor).
    # `block` zaten yedegi hesaba katar (bkz. _build_usage_info) — zincirde kilitlenmez (L6).
    if pre_usage.block:
        # BUG #188: kullaniciya IC YAPILANDIRMA tavsiyesi verilmez (eskiden .env/saglayici
        # adi yaziyordu — son kullanici icin anlamsiz, ic mimariyi ifsa eder).
        raise HTTPException(
            status_code=429,
            detail="Koc su an yogun (gunluk kapasite doldu). Yarin yeniden dene — "
                   "paneller ve hesaplamalar calismaya devam ediyor.",
        )

    # BUG #263 (P5.5) KAPASITE: eszamanli LLM cagrisi TAVANLI. Bir kocu mesaji iki-gecis
    # mimarisi yuzunden 2 LLM cagrisi yapar ve bu sure boyunca (10-40 sn) DB baglantisini
    # ELDE TUTAR; tavansiz birakilirsa 15 eszamanli koc istegi process'in TUM havuzunu
    # kilitler ve /api/ready dahil her sey 500'e duser. Slot CAGRI ONCESI ve KOTA
    # REZERVASYONUNDAN ONCE alinir — reddedilen istek kullanicinin gunluk hakkini YAKMAZ.
    # `KapasiteDolu` bilerek asagidaki try'in DISINDA kalir: nazik 503'tur, "kocun cevap
    # veremedi" degil (app/main.py'deki ozel handler).
    with kapasite.yavas_yol(kapasite.LLM):
        # BUG #212 (H17): sayaci CAGRI ONCESI rezerve et — eszamanli istekler tavani delmesin.
        rezervasyon = _kota_rezerve_et(db, user.id, provider_name, model, kisisel_tavan)

        # Asil cagri + sure olcumu
        t_start = time.time()
        success = True
        error_msg = None
        tool_calls_count = 0

        # BUG #234 (D15): tavanin birimi ÇAĞRI'dır. Bir mesaj iki-geçiş + retry + zincir
        # yüzünden 1-4 GERÇEK istek üretir; ölçüm kapsamı bunları sayar, aşağıda uzlaştırılır.
        olcum: Dict[str, int] = {}
        try:
            with _kota.cagri_olcumu() as olcum:
                with workspace_scope(ws_id):  # M43: koç bağlamı (cockpit) aktif workspace'ten
                    result = engine.chat(
                        db=db,
                        user_id=user.id,
                        user_message=payload.message,
                        include_cockpit=payload.include_cockpit,
                        workspace_id=ws_id,
                    )
            tool_calls_count = len(result.get("proposed_actions") or [])
        except Exception as e:
            # BE-009 fix: graceful degradation (chat UX için 200) AMA ham hata (str(e)) kullanıcıya
            # SIZDIRILMAZ — güvenlik/profesyonellik. Gerçek hata error_msg olarak LOGLANIR.
            success = False
            error_msg = str(e)
            logger.error("coach chat başarısız user_id=%s: %s", user.id, e, exc_info=True)
            result = {
                "reply": "Koç şu an cevap veremedi (sağlayıcılar meşgul olabilir). Birazdan tekrar dene.",
                "proposed_actions": [],
                "cockpit_snapshot": None,
            }

    duration_ms = int((time.time() - t_start) * 1000)
    # BE-025: nominal "fallback" yerine İSTEĞE FİİLEN CEVAP VEREN alt-sağlayıcıyı logla →
    # günlük Gemini kotası doğru izlenir (aksi halde her çağrı "fallback" loglanıp gemini
    # sayacı hep 0 kalır, günlük-limit koruması ölür).
    logged_provider = (result.get("provider_used") or provider_name)
    _rezervasyonu_tamamla(
        db, rezervasyon, logged_provider,
        success=success, duration_ms=duration_ms,
        tool_calls_count=tool_calls_count, error_message=error_msg,
    )
    # BUG #234 (D15): rezervasyon TEK satır yazar; gerçek istek sayısı ancak burada bilinir.
    # Fark kadar ek satır, isteği fiilen yiyen sağlayıcı adına yazılır.
    _kota.ek_cagrilari_uzlastir(db, user.id, olcum, rezervasyon, model)

    # Post-call usage (yeni log dahil)
    post_usage = _build_usage_info(db, user.id, provider_name, alternatif_var=yedek_var)

    return ChatResponse(
        reply=result["reply"],
        proposed_actions=[
            ProposedActionOut(**pa) for pa in (result.get("proposed_actions") or [])
        ],
        cockpit_snapshot=result.get("cockpit_snapshot"),
        usage=post_usage,
        coach_memory_id=result.get("coach_memory_id"),
    )


@router.get("/history", response_model=List[HistoryItem])
def get_history(
    limit: int = Query(50, ge=1, le=500),  # BUG #154 (P2-5): ust sinir
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

    # BUG #046: Batch pending action lookup — N+1 yok
    all_pa_ids: List[int] = []
    for m in items:
        if m.pending_action_ids_json:
            try:
                all_pa_ids.extend(json.loads(m.pending_action_ids_json))
            except Exception:
                # BE-010: bozuk pending_action_ids_json → atla ama debug'a yaz (tanılanabilir).
                logger.debug("pending_action_ids_json parse edilemedi memory=%s",
                             getattr(m, "id", "?"), exc_info=True)
    pa_map: Dict[int, PendingAction] = {}
    if all_pa_ids:
        # P1 (Wave-9) sertleştirme: id listesi kullanıcının KENDİ hafıza satırlarından geliyor,
        # yine de sorgu sahibe kapsanır — bozuk/elle düzenlenmiş bir memory satırı başka
        # kullanıcının aksiyon özetini geçmişte gösteremesin (savunma derinliği).
        pas = db.query(PendingAction).filter(
            PendingAction.id.in_(all_pa_ids),
            PendingAction.user_id == user.id,  # scope-exempt: koç geçmişi kişisel-bağlı (workspace paylaşımı yok)
        ).all()
        pa_map = {pa.id: pa for pa in pas}

    items_mapped = [_memory_to_history_item(m, pa_map) for m in items]
    return [it for it in items_mapped if it is not None]


@router.get("/trace/{memory_id}", response_model=TraceResponse)
def get_trace(
    memory_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TraceResponse:
    """Return the reasoning trace for one of the current user's CoachMemory rows.

    Industry-standard resource-hiding: an unauthorized memory_id and a
    memory_id without a recorded trace are both 404 (OWASP/REST best
    practice — never disclose existence of another user's resource).
    """
    steps = (
        db.query(ReasoningTrace)
        .filter(
            ReasoningTrace.coach_memory_id == memory_id,
            ReasoningTrace.user_id == user.id,
        )
        .order_by(ReasoningTrace.step_index.asc())
        .all()
    )
    if not steps:
        raise HTTPException(status_code=404, detail="Trace bulunamadi")

    return TraceResponse(
        coach_memory_id=memory_id,
        trace_id=steps[0].trace_id,
        steps=[
            TraceStepOut(
                id=s.id,
                step_index=s.step_index,
                parent_step_id=s.parent_step_id,
                operation_name=s.operation_name.value,
                intent=s.intent,
                action_input_json=s.action_input_json,
                observation=s.observation,
                inference=s.inference,
                confidence_score=s.confidence_score,
                provider_system=s.provider_system,
                model_name=s.model_name,
                usage_input_tokens=s.usage_input_tokens,
                usage_output_tokens=s.usage_output_tokens,
                latency_ms=s.latency_ms,
                error=s.error,
                created_at=s.created_at,
            )
            for s in steps
        ],
    )


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
    # BUG #234: etiket calisma-ani durumundan degil yapilandirmadan turetilir — `provider_name`
    # ilk basarili cagridan sonra "Fallback(Gemini)" doner, o etiket PROVIDER_DAILY_LIMITS'te
    # yoktur ve rozet sessizce %0'a duserdi (BUG #212 ile ayni sinif).
    provider_name = _muhasebe_saglayici_adi(engine)
    return _build_usage_info(db, user.id, provider_name,
                             alternatif_var=_alternatif_saglayici_var(engine))