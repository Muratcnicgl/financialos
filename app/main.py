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


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# STARTUP CATCH-UP
# ============================================================

def _catch_up_snapshots() -> None:
    """App acilisinda eksik NetWorthSnapshot gunlerini doldur.

    Mantik: last_snapshot_date < bugun ise araligi doldur.
    Idempotent (backfill upsert kullanir, ayni tarih yazilirsa eskisini ezer).
    Hata olursa app acilmasi engellenmemeli - cagiran try/except ile sarar.
    """
    from scripts.backfill_net_worth import run_backfill

    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.id.asc()).first()
        if not user:
            logger.info("Catch-up: Kullanici yok, atlandi")
            return

        last_date = (
            db.query(func.max(NetWorthSnapshot.snapshot_date))
            .filter(NetWorthSnapshot.user_id == user.id)
            .scalar()
        )
        if last_date is None:
            logger.info("Catch-up: Hic snapshot yok, manuel backfill gerekli "
                        "(python -m scripts.backfill_net_worth)")
            return

        today = date.today()
        start = last_date + timedelta(days=1)
        if start > today:
            logger.info(f"Catch-up: Snapshot guncel ({last_date}), atlandi")
            return

        n_days = (today - start).days + 1
        logger.info(f"Catch-up: Eksik {n_days} gun bulundu ({start} -> {today}), "
                    f"backfill calistiriliyor...")
        written = run_backfill(start, today, verbose=False)
        logger.info(f"Catch-up: {written} snapshot yazildi")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: catch-up backfill (eksik gunleri doldur)
    # ADR-013: Schema yonetimi alembic ile, burada sadece runtime is mantigi.
    logger.info("Backend baslatildi. Schema: alembic upgrade head ile.")
    try:
        _catch_up_snapshots()
    except Exception as e:
        # App acilmasi engellenmemeli, sessizce log'la
        logger.warning(f"Catch-up backfill hatasi: {type(e).__name__}: {e}")

    yield
    # Shutdown: ozel temizlik gerekmez


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
