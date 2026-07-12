"""
Startup runtime iş mantığı.

app/PROJE.md kuralı: main.py küçük tutulur (app yaratımı, CORS, router kayıt); iş
mantığı buraya girmez. Açılışta çalışan backfill/catch-up gibi mantık bu modülde toplanır;
main.py'nin lifespan'ı yalnızca çağırır.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func

from app.database import SessionLocal
from app.models import NetWorthSnapshot, User

logger = logging.getLogger(__name__)


def catch_up_snapshots() -> None:
    """App açılışında eksik NetWorthSnapshot günlerini doldur.

    Mantık: last_snapshot_date < bugün ise aralığı doldur.
    Idempotent (backfill upsert kullanır, aynı tarih yazılırsa eskisini ezer).
    Hata olursa app açılması engellenmemeli — çağıran try/except ile sarar.
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
