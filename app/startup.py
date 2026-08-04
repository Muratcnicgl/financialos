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
    """App açılışında eksik NetWorthSnapshot günlerini doldur — HER kullanıcı için.

    Mantık: kullanıcının last_snapshot_date'i < bugün ise o kullanıcının aralığı doldurulur.
    Idempotent (backfill upsert kullanır, aynı tarih yazılırsa eskisini ezer).
    Hata olursa app açılması engellenmemeli — çağıran try/except ile sarar.

    BUG #163 fix: eskiden yalnız ilk kullanıcı (`User.id` en küçük) işleniyordu; çok-kullanıcıda
    diğer kullanıcıların net-değer geçmişinde kalıcı boşluklar oluşuyordu (trend/atıf raporları
    sessizce eksik). Kullanıcı başına ayrı aralık hesaplanır — herkesin kendi boşluğu kadar.
    """
    from scripts.backfill_net_worth import run_backfill

    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id.asc()).all()
        if not users:
            logger.info("Catch-up: Kullanici yok, atlandi")
            return

        today = date.today()
        for user in users:  # BUG #163: tüm kullanıcılar
            last_date = (
                db.query(func.max(NetWorthSnapshot.snapshot_date))
                .filter(NetWorthSnapshot.user_id == user.id)
                .scalar()
            )
            if last_date is None:
                logger.info("Catch-up: user %s icin hic snapshot yok, manuel backfill gerekli "
                            "(python -m scripts.backfill_net_worth)", user.id)
                continue

            start = last_date + timedelta(days=1)
            if start > today:
                logger.info("Catch-up: user %s guncel (%s), atlandi", user.id, last_date)
                continue

            n_days = (today - start).days + 1
            logger.info("Catch-up: user %s icin eksik %s gun (%s -> %s), backfill calistiriliyor...",
                        user.id, n_days, start, today)
            written = run_backfill(start, today, verbose=False, user_id=user.id)
            logger.info("Catch-up: user %s icin %s snapshot yazildi", user.id, written)
    finally:
        db.close()
