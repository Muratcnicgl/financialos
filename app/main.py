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
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine

# === Router'lar ===
# Grup 1: kullanici + hesaplar
from app.routers import user as user_router
from app.routers import accounts as accounts_router
# Grup 2: islemler + gelirler + borclar + kirmizi cizgiler
from app.routers import transactions as transactions_router
from app.routers import incomes as incomes_router
from app.routers import debts as debts_router
from app.routers import checkpoints as checkpoints_router
# Grup 3: cockpit + coach + actions + fund_price (KOC CANLANIYOR!)
from app.routers import cockpit as cockpit_router
from app.routers import coach as coach_router
from app.routers import actions as actions_router
from app.routers import fund_price as fund_price_router

# Grup 4: yazilacak (henuz import etmiyoruz)
# from app.routers import simulation, reports, alerts, backup


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# APP YARATIMI
# ============================================================

app = FastAPI(
    title="FinancialOS API",
    description="160 IQ stratejik finansal koc — backend.",
    version="0.1.0",
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
# DB INIT
# ============================================================

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    logger.info("DB hazir. Tum tablolar mevcut.")


# ============================================================
# ROUTER KAYIT
# ============================================================

# Grup 1
app.include_router(user_router.router)
app.include_router(accounts_router.router)
# Grup 2
app.include_router(transactions_router.router)
app.include_router(incomes_router.router)
app.include_router(debts_router.router)
app.include_router(checkpoints_router.router)
# Grup 3
app.include_router(cockpit_router.router)
app.include_router(coach_router.router)
app.include_router(actions_router.router)
app.include_router(fund_price_router.router)

# Grup 4'te eklenecek:
# app.include_router(simulation_router.router)
# app.include_router(reports_router.router)
# app.include_router(alerts_router.router)
# app.include_router(backup_router.router)


# ============================================================
# SAGLIK KONTROLLERI
# ============================================================

def _health_payload() -> dict:
    return {
        "status": "ok",
        "service": "FinancialOS",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
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