"""
FinancialOS — SQLite yedekleme scripti.

Kullanim:
    python -m scripts.backup              # data/backups/YYYY-MM-DD-HHMM.db
    python -m scripts.backup --keep-days 7   # 7 gunden eskiyi sil

SQLite online backup API kullanilir (Connection.backup) — canli DB bozulmaz,
aktif transaction'larla uyumlu.
"""

import argparse
import glob
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path


DB_PATH     = Path("data/financialos.db")
BACKUP_DIR  = Path("data/backups")


def backup(keep_days: int = 30) -> None:
    if not DB_PATH.exists():
        print(f"HATA: DB bulunamadi: {DB_PATH}")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    stamp  = datetime.now().strftime("%Y-%m-%d-%H%M")
    dest   = BACKUP_DIR / f"{stamp}.db"

    # Online backup — kaynak DB kilitlenmez, transaction'lar tutarli kopyalanir
    src_conn  = sqlite3.connect(DB_PATH)
    dest_conn = sqlite3.connect(dest)
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    size_kb = dest.stat().st_size // 1024
    print(f"Yedek alindi: {dest}  ({size_kb} KB)")

    # Eski yedekleri temizle
    cutoff   = time.time() - keep_days * 86400
    old_files = [
        f for f in glob.glob(str(BACKUP_DIR / "*.db"))
        if os.path.getmtime(f) < cutoff
    ]
    for f in old_files:
        os.remove(f)

    if old_files:
        print(f"{len(old_files)} eski yedek silindi (>{keep_days} gun).")
    else:
        print(f"Silinecek eski yedek yok (keep_days={keep_days}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinancialOS SQLite yedekleme")
    parser.add_argument(
        "--keep-days", type=int, default=30,
        help="Kac gunluk yedek saklansin (default: 30)"
    )
    args = parser.parse_args()
    backup(keep_days=args.keep_days)
