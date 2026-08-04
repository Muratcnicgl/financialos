"""
FinancialOS — FastAPI uygulamasi.

Mimari: main.py kucuk, sadece app yaratimi + CORS + router'lari kayit.
Endpoint'ler app/routers/ altindaki dosyalardadir, her dosya bir konuya odaklanir.

Calistirma:
    uvicorn app.main:app --reload --port 8000

Saglik kontrolu:
    GET  http://localhost:8000/         -> {"status": "ok", ...}  (root)
    GET  http://localhost:8000/api/health -> ayni cevap (frontend proxy uzerinden)
    GET  http://localhost:8000/docs     -> Swagger UI (interaktif test)
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from app.database import SessionLocal
from app.version import APP_VERSION as _APP_VERSION, build_commit as _build_commit  # P9
from app.models import NetWorthSnapshot, User

# === Router'lar ===
# Grup 1: kullanici + hesaplar
from app.routers import user as user_router
from app.routers import accounts as accounts_router
# Grup 2: islemler + gelirler + giderler + borclar + kirmizi cizgiler
from app.routers import transactions as transactions_router
from app.routers import incomes as incomes_router
from app.routers import expenses as expenses_router  # A3: RecurringExpense
from app.routers import debts as debts_router
from app.routers import checkpoints as checkpoints_router
# Grup 3: cockpit + coach + actions + fund_price (KOC CANLANIYOR!)
from app.routers import cockpit as cockpit_router
from app.routers import coach as coach_router
from app.routers import actions as actions_router
from app.routers import fund_price as fund_price_router

# Grup 4
from app.routers import reports as reports_router
from app.routers import cashflow as cashflow_router
from app.routers import premortem as premortem_router
from app.routers import simulation as simulation_router
from app.routers import debt_strategy as debt_strategy_router

# M11: Auth + Multi-user (ADR-033)
from app.routers import auth as auth_router
# M19: Fiyat sorgulama (EVDS döviz/altın)
from app.routers import prices as prices_router
# Grup 5: H2G5 Goal Engine
from app.routers import goals as goals_router
from app.routers import subscriptions as subscriptions_router  # FEAT-006
from app.routers import envelopes as envelopes_router  # FEAT-001
from app.routers import wishlist as wishlist_router  # FEAT-032
from app.routers import workspaces as workspaces_router  # M41 (ADR-036)
from app.routers import feedback as feedback_router  # FEAT-033


# ============================================================
# LOGGING
# ============================================================

# M23: merkezi logging (console + rotating file, prod JSON/dev text)
from app.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)


# ============================================================
# STARTUP CATCH-UP — iş mantığı app/startup.py'de (main.py küçük kalsın, app/PROJE.md)
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    # M16 (BUG #157): güvenlik config fail-fast — production'da eksik/zayıf SECRET_KEY
    # ile uygulama açılmaz (startup'ta, ilk auth isteğinde değil).
    from app.settings import validate_security_config
    validate_security_config()

    # Startup: catch-up backfill (eksik gunleri doldur)
    # ADR-013: Schema yonetimi alembic ile, burada sadece runtime is mantigi.
    logger.info("Backend baslatildi. Schema: alembic upgrade head ile.")
    try:
        from app.startup import catch_up_snapshots
        catch_up_snapshots()
    except Exception as e:
        # App acilmasi engellenmemeli, sessizce log'la
        logger.warning(f"Catch-up backfill hatasi: {type(e).__name__}: {e}")

    # Davranissal hafiza scheduler'i baslat
    # MA1 (Wave-8): SCHEDULER_ENABLED gate — production'da gunicorn ÇOK worker çalıştırır; APScheduler
    # her worker'da başlarsa cron N kez tetiklenir (çift fiyat/batch). Prod'da web worker'ları
    # SCHEDULER_ENABLED=false, ayrı bir "scheduler" servisi SCHEDULER_ENABLED=true ile TEK scheduler koşar.
    # Dev/tek-process (uvicorn) default AÇIK (geriye uyum) — env verilmemişse true.
    _sched_on = os.getenv("SCHEDULER_ENABLED", "true").strip().lower() not in ("0", "false", "no")
    _scheduler_started = False
    if _sched_on:
        from app.scheduler import start_scheduler
        try:
            start_scheduler()
            _scheduler_started = True
        except Exception as e:
            logger.warning(f"Scheduler baslatilamadi: {type(e).__name__}: {e}")
    else:
        logger.info("[scheduler] SCHEDULER_ENABLED=false → bu process'te scheduler başlatılmadı (ayrı servis koşar).")

    yield

    # Shutdown: scheduler'i durdur (yalnız başlatıldıysa)
    if _scheduler_started:
        try:
            from app.scheduler import shutdown_scheduler
            shutdown_scheduler()
        except Exception as e:
            logger.warning(f"Scheduler durdurma hatasi: {type(e).__name__}: {e}")


# ============================================================
# APP YARATIMI
# ============================================================

# M34 (SEC-015): production'da /docs, /redoc, /openapi.json KAPALI (bilgi ifşası önlenir).
# Development'ta açık (geliştirici kolaylığı).
from app.settings import is_production as _is_prod
_docs_disabled = _is_prod()
app = FastAPI(
    title="FinancialOS API",
    description="160 IQ stratejik finansal koc — backend.",
    version=_APP_VERSION,   # P9: tek kaynak app/version.py
    lifespan=lifespan,
    docs_url=None if _docs_disabled else "/docs",
    redoc_url=None if _docs_disabled else "/redoc",
    openapi_url=None if _docs_disabled else "/openapi.json",
)


# ============================================================
# CORS
# ============================================================

# W3-040 (SEC-003/MN-002): origin'ler artık env-driven (prod domain'i CORS_ORIGINS ile
# verilir), dev default localhost. Methods/headers wildcard yerine açık liste —
# allow_credentials=True ile wildcard origin zaten yasak; en az yetki ilkesi.
_DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173,http://localhost:3000,"
    "http://127.0.0.1:5173,http://127.0.0.1:3000"
)
def _compute_cors_origins() -> list[str]:
    """M22: CORS_ORIGINS varsa onu; yoksa dev default + (varsa) FRONTEND_URL.

    Prod'da tek `FRONTEND_URL` yeterli olsun (CORS_ORIGINS ayrıca zorunlu olmasın).
    """
    explicit = os.getenv("CORS_ORIGINS", "").strip()
    if explicit:
        return [o.strip() for o in explicit.split(",") if o.strip()]
    frontend = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
    # BUG #178 (P2): production'da localhost fallback'i YASAK. Önerilen prod kurulumda
    # (aynı-origin nginx → CORS_ORIGINS boş) backend, kurbanın makinesindeki herhangi bir
    # yerel geliştirme sunucusuna credentialed CORS izni veriyordu (en-az-yetki ihlali).
    from app.settings import is_production
    if is_production():
        return [frontend] if frontend else []
    origins = [o.strip() for o in _DEFAULT_CORS_ORIGINS.split(",") if o.strip()]
    if frontend and frontend not in origins:
        origins.append(frontend)
    return origins


_cors_origins = _compute_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ============================================================
# HATA IZLEME (P5 / BUG #195)
# ============================================================
# Beklenmedik hata YALNIZ log dosyasina dusuyordu; kapali betada operator log'u surekli
# izleyemez -> hata sessizce yasar. Artik kendi DB'mize kaydedilir (dis servise veri gitmez).

from fastapi import Request as _Request
from fastapi.responses import JSONResponse as _JSONResponse


@app.exception_handler(Exception)
async def _beklenmedik_hata(request: _Request, exc: Exception):
    from app.database import SessionLocal as _SL
    from app.error_tracking import kaydet as _kaydet
    user_id = None
    try:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            from app import auth as _a
            user_id = int(_a.decode_token(auth[7:].strip(), expected_type="access")["sub"])
    except Exception:
        user_id = None
    db = _SL()
    try:
        _kaydet(db, hata=exc, yol=str(request.url.path), metod=request.method, user_id=user_id)
    finally:
        db.close()
    logger.exception("Beklenmedik hata: %s %s", request.method, request.url.path)
    # BUG #175 ile tutarli: kullaniciya IC DETAY sizmaz.
    return _JSONResponse(
        status_code=500,
        content={"detail": "Beklenmedik bir hata oluştu. Kayıt altına alındı."},
    )


# ============================================================
# ROUTER KAYIT
# ============================================================

# Grup 1
from app.routers import legal as legal_router  # P4: hukuki metinler (kimliksiz erisim)
app.include_router(legal_router.router)
from app.routers import onboarding as onboarding_router  # P3.5/H5: opsiyonel demo veri
app.include_router(onboarding_router.router)
app.include_router(user_router.router)
app.include_router(accounts_router.router)
# Grup 2
app.include_router(transactions_router.router)
app.include_router(incomes_router.router)
app.include_router(expenses_router.router)
app.include_router(debts_router.router)
app.include_router(checkpoints_router.router)
# Grup 3
app.include_router(cockpit_router.router)
app.include_router(coach_router.router)
app.include_router(actions_router.router)
app.include_router(fund_price_router.router)

# Grup 4
app.include_router(reports_router.router)
app.include_router(cashflow_router.router)
app.include_router(premortem_router.router)
app.include_router(simulation_router.router)
app.include_router(debt_strategy_router.router)

# Grup 5
app.include_router(goals_router.router)
app.include_router(subscriptions_router.router)  # FEAT-006
app.include_router(envelopes_router.router)  # FEAT-001
app.include_router(wishlist_router.router)  # FEAT-032
# M11: Auth + Multi-user (ADR-033)
app.include_router(auth_router.router)         # /api/auth
app.include_router(auth_router.users_router)   # /api/users (KVKK sil/export)
app.include_router(prices_router.router)       # /api/prices (EVDS döviz/altın)
app.include_router(workspaces_router.router)   # M41: /api/workspaces (ADR-036)
app.include_router(feedback_router.router)     # FEAT-033: /api/feedback


# ============================================================
# SAGLIK KONTROLLERI
# ============================================================

def _health_payload() -> dict:
    from app.auth import auth_enabled
    return {
        "status": "ok",
        "service": "FinancialOS",
        # BUG #200 (P9): surum SABIT "0.1.0" idi -> canlida hangi kodun kostugu
        # olculemiyordu (hata bildirimi, deploy dogrulamasi, geri alma sonrasi kontrol).
        "version": _APP_VERSION,
        "build": _build_commit(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "auth_enabled": auth_enabled(),  # M11: frontend login gate'i buna bakar
    }


@app.get("/", tags=["health"])
def root():
    """Backend kok adresi. Direkt tarayici testleri icin."""
    return _health_payload()


@app.get("/api/health", tags=["health"])
def api_health():
    """
    Frontend saglik kontrolu — vite proxy /api/* uzerinden buraya gelir.
    Frontend'in 'Backend kapali' rozetinin tam tersine 'cevap geliyor' demesi
    icin gerekli. Root '/' Vite'in kendi sayfasi olduguntan proxy gecmiyor.
    """
    return _health_payload()
