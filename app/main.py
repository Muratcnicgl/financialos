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
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from app.database import SessionLocal
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

# Grup 5: H2G5 Goal Engine
from app.routers import goals as goals_router
from app.routers import subscriptions as subscriptions_router  # FEAT-006
from app.routers import envelopes as envelopes_router  # FEAT-001
from app.routers import wishlist as wishlist_router  # FEAT-032


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# STARTUP CATCH-UP — iş mantığı app/startup.py'de (main.py küçük kalsın, app/PROJE.md)
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    from app.scheduler import start_scheduler, shutdown_scheduler
    try:
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler baslatilamadi: {type(e).__name__}: {e}")

    yield

    # Shutdown: scheduler'i durdur
    try:
        shutdown_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler durdurma hatasi: {type(e).__name__}: {e}")


# ============================================================
# APP YARATIMI
# ============================================================

app = FastAPI(
    title="FinancialOS API",
    description="160 IQ stratejik finansal koc — backend.",
    version="0.1.0",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTER KAYIT
# ============================================================

# Grup 1
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


# ============================================================
# SAGLIK KONTROLLERI
# ============================================================

def _health_payload() -> dict:
    return {
        "status": "ok",
        "service": "FinancialOS",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
