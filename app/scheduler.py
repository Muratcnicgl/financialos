"""
FinancialOS Davranissal Hafiza - Tetikleme Altyapisi
====================================================

Sektor temeli:
- AsyncIOScheduler FastAPI lifespan ile ayni event loop'u paylasir (GitHub
  apscheduler discussion #830, nashruddinamin.com 2024).
- BackgroundScheduler thread overhead yaratir, gerekmiyorsa kacin.
- Olay-tetikli extractor'lar fire-and-forget asyncio.create_task ile - Coach
  response gecikmemeli.

Iki tetikleme hatti:
1. Periyodik (gece batch) - APScheduler cron jobs
   - 03:00 Istanbul: breakthrough, setback, mc_reference_frequency,
                     question_typology, category_account_preference
   - 03:30 Istanbul: explicit_red_line_k2 (K1 olay-tetiklemesinden sonra)
2. Olay-tetikli (anlik)
   - Yeni user mesaji: explicit_red_line_k1, decision_rhythm
   - PendingAction status degisikligi (rejected/executed): action_rejection_pattern

Multi-user destegi: gece batch tum aktif user'lari DB'den cekip her biri icin
extractor'lari sirayla calistirir. Bir extractor cokerse digerleri etkilenmez.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from sqlalchemy import delete
from app.models import User, ReasoningTrace
from app.coach_insights import (
    extract_breakthrough,
    extract_setback,
    extract_mc_reference_frequency,
    extract_question_typology,
    extract_category_account_preference,
    extract_explicit_red_line_k2,
    extract_explicit_red_line_k1,
    extract_decision_rhythm,
    extract_action_rejection_pattern,
)

logger = logging.getLogger(__name__)

# Singleton scheduler - lifespan tarafindan baslatilip durdurulacak
_scheduler: AsyncIOScheduler | None = None

# Periyodik batch icin extractor isimlerinin sirasi
NIGHTLY_BATCH_EXTRACTORS = [
    "breakthrough",
    "setback",
    "mc_reference_frequency",
    "question_typology",
    "category_account_preference",
]

# K2 ayri job - K1 olay-tetiklemesinden sonra calismali (zaman gecikmeli)
K2_BATCH_EXTRACTOR = "explicit_red_line_k2"

# Olay-tetikli extractor'lar
EVENT_TRIGGERED_AFTER_USER_MESSAGE = [
    "explicit_red_line_k1",
    "decision_rhythm",
]
EVENT_TRIGGERED_AFTER_ACTION_RESOLUTION = [
    "action_rejection_pattern",
]


@contextmanager
def _db_session() -> Iterator[Session]:
    """Scheduler job'larinin kendi DB session'i. Lifecycle scope kontrollu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_extractor(name: str, db: Session, user_id: int) -> dict:
    """
    Tek extractor calistir, imza farklarini hide et, hata izolasyonu sagla.
    9 extractor 3 farkli imza tipi:
    - 7 tanesi: (db, user_id) -> dict
    - decision_rhythm: (db, user_id) -> None
    - explicit_red_line_k2: (db, user_id, provider=None) -> dict
    """
    try:
        if name == "breakthrough":
            return extract_breakthrough(db, user_id) or {}
        elif name == "setback":
            return extract_setback(db, user_id) or {}
        elif name == "mc_reference_frequency":
            return extract_mc_reference_frequency(db, user_id) or {}
        elif name == "question_typology":
            return extract_question_typology(db, user_id) or {}
        elif name == "category_account_preference":
            return extract_category_account_preference(db, user_id) or {}
        elif name == "explicit_red_line_k1":
            return extract_explicit_red_line_k1(db, user_id) or {}
        elif name == "explicit_red_line_k2":
            return extract_explicit_red_line_k2(db, user_id, provider=None) or {}
        elif name == "decision_rhythm":
            extract_decision_rhythm(db, user_id)
            return {"status": "completed"}  # decision_rhythm None doner, normalize
        elif name == "action_rejection_pattern":
            return extract_action_rejection_pattern(db, user_id) or {}
        else:
            return {"error": f"unknown_extractor: {name}"}
    except Exception as e:
        # BUG #062 fix (SC-001): hatada session'i temizle. Yoksa bir extractor commit'te
        # patlarsa paylaşılan db "PendingRollback"a düşer ve sonraki extractor'lar/Coach'un
        # _save_message'i sessizce/patlayarak çalışmaz (docstring'in "izolasyon" vaadi ihlaliydi).
        db.rollback()
        logger.exception(f"Extractor {name} failed for user {user_id}: {e}")
        return {"error": str(e)[:200], "extractor": name}


def run_periodic_batch_for_user(db: Session, user_id: int) -> dict:
    """Tek user icin gece batch extractor'larini sirayla calistir.
    Bir extractor coker diger 4'u devam eder."""
    results = {}
    for name in NIGHTLY_BATCH_EXTRACTORS:
        results[name] = run_extractor(name, db, user_id)
    return results


def run_k2_batch_for_user(db: Session, user_id: int) -> dict:
    """K2 ayri job - K1 olay-tetikleme sonrasi calismali."""
    return {K2_BATCH_EXTRACTOR: run_extractor(K2_BATCH_EXTRACTOR, db, user_id)}


def _get_active_user_ids(db: Session) -> list[int]:
    """Aktif user'lari getir. Su an User tablosu is_active filtresi yok,
    tum kayitli user'lari dondur."""
    users = db.query(User).all()
    return [u.id for u in users]


async def nightly_batch_job():
    """APScheduler cron job - gece 03:00 calisir, tum user'lar icin batch."""
    logger.info(f"Nightly batch job started at {datetime.utcnow().isoformat()}")
    try:
        with _db_session() as db:
            user_ids = _get_active_user_ids(db)
            for uid in user_ids:
                results = run_periodic_batch_for_user(db, uid)
                logger.info(f"Nightly batch for user {uid}: {results}")
    except Exception as e:
        logger.exception(f"Nightly batch job failed globally: {e}")
    logger.info(f"Nightly batch job completed at {datetime.utcnow().isoformat()}")


async def k2_batch_job():
    """APScheduler cron job - gece 03:30, K2 LLM consolidation."""
    logger.info(f"K2 batch job started at {datetime.utcnow().isoformat()}")
    try:
        with _db_session() as db:
            user_ids = _get_active_user_ids(db)
            for uid in user_ids:
                results = run_k2_batch_for_user(db, uid)
                logger.info(f"K2 batch for user {uid}: {results}")
    except Exception as e:
        logger.exception(f"K2 batch job failed globally: {e}")
    logger.info(f"K2 batch job completed at {datetime.utcnow().isoformat()}")


async def nightly_trace_cleanup_job() -> None:
    """
    Reasoning trace retention job.

    Deletes ReasoningTrace rows older than 90 days. Runs at 04:00
    Istanbul daily (after nightly_batch and k2_batch). 90-day
    retention follows the warm-tier convention used by Langfuse
    and similar LLM observability stacks — long enough for audit
    and debugging, short enough to keep the single-file SQLite
    database lean. Idempotent: re-running has no effect if the
    table is already trimmed.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        stmt = delete(ReasoningTrace).where(
            ReasoningTrace.created_at < cutoff
        )
        result = db.execute(stmt)
        db.commit()
        deleted = result.rowcount or 0
        logger.info(
            "[trace_cleanup] removed %d reasoning_trace rows older than %s",
            deleted,
            cutoff.isoformat(),
        )
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("[trace_cleanup] failed; rolled back transaction")
        raise
    finally:
        db.close()


async def fetch_investment_prices_job() -> None:
    """
    Günlük yatırım fiyat çekimi (M4 / ADR-029). Tüm `investment` hesaplarının fiyatını
    çeker (fund_code → TEFAS/pytefas), `Account.current_price` + `PriceHistory` günceller.
    Idempotent (ADR-012 kompozit PK). Gece **02:45** — nightly_batch (03:00) ÖNCESİ, böylece
    batch analizi/cockpit taze fiyatla çalışır. TEFAS ~18:00 yayınladığından sabah dünün fiyatı.
    """
    from app.price_providers import fetch_for_account, record_investment_price
    from app.models import Account, AccountType
    db = SessionLocal()
    try:
        accounts = db.query(Account).filter(Account.account_type == AccountType.investment).all()
        updated = 0
        for acc in accounts:
            try:
                res = fetch_for_account(acc)
            except Exception:
                logger.exception("[price] %s (%s) çekim hatası", acc.name, acc.fund_code)
                res = None
            if res:
                price, source = res
                record_investment_price(db, acc, price, source)
                updated += 1
                logger.info("[price] %s (%s) = %s [%s]", acc.name, acc.fund_code, price, source)
            else:
                logger.warning("[price] %s (%s): fiyat çekilemedi (elle giriş gerekebilir)",
                               acc.name, acc.fund_code)
        logger.info("[price] %d/%d yatırım hesabı güncellendi", updated, len(accounts))
    except Exception:
        db.rollback()
        logger.exception("[price] fetch_investment_prices_job başarısız")
    finally:
        db.close()


def start_scheduler() -> AsyncIOScheduler:
    """Lifespan startup'tan cagirilir."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="Europe/Istanbul")

    _scheduler.add_job(
        fetch_investment_prices_job,
        CronTrigger(hour=2, minute=45),
        id="fetch_investment_prices",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        nightly_batch_job,
        CronTrigger(hour=3, minute=0),
        id="nightly_batch",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 saat icinde gecikirse yine calistir
    )
    _scheduler.add_job(
        k2_batch_job,
        CronTrigger(hour=3, minute=30),
        id="k2_batch",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        nightly_trace_cleanup_job,
        CronTrigger(hour=4, minute=0),
        id="nightly_trace_cleanup",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info("FinancialOS scheduler started: nightly_batch 03:00, k2_batch 03:30, trace_cleanup 04:00 Istanbul")
    return _scheduler


def shutdown_scheduler() -> None:
    """Lifespan shutdown'tan cagirilir."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("FinancialOS scheduler shut down")
        _scheduler = None


# ============================================================
# Olay-tetikli extractor cagrilari (Coach + ActionExecutor'dan kullanilacak)
# ============================================================

def trigger_after_user_message(db: Session, user_id: int) -> None:
    """
    Coach._save_message user role kaydi sonrasinda cagrilir.
    explicit_red_line_k1 + decision_rhythm sirayla calistirir, sync.
    Hata izolasyonu: cokerse Coach response'u etkilemez.

    NOT: Su an sync, Coach.chat() icinden cagrilacak. Performance sorunu olursa
    asyncio.create_task ile fire-and-forget'e cevirilebilir.
    """
    for name in EVENT_TRIGGERED_AFTER_USER_MESSAGE:
        try:
            run_extractor(name, db, user_id)
        except Exception as e:
            logger.warning(f"Event-triggered {name} failed for user {user_id}: {e}")


def trigger_after_action_resolution(db: Session, user_id: int) -> None:
    """
    PendingAction status degisikligi (rejected/executed) sonrasinda cagrilir.
    action_rejection_pattern calistirir.
    """
    for name in EVENT_TRIGGERED_AFTER_ACTION_RESOLUTION:
        try:
            run_extractor(name, db, user_id)
        except Exception as e:
            logger.warning(f"Event-triggered {name} failed for user {user_id}: {e}")
