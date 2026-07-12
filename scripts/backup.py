"""
FinancialOS — SQLite yedekleme scripti.

Kullanim:
    python -m scripts.backup              # data/backups/YYYY-MM-DD-HHMMSS.db
    python -m scripts.backup --keep-days 7   # 7 gunden eskiyi sil

SQLite online backup API kullanilir (Connection.backup) — canli DB bozulmaz,
aktif transaction'larla uyumlu.

GUNCELLEMELER:
- 6 Tem 2026 BUG #075 fix (SBK-001..007): DB yolu DATABASE_URL'den turetilir
  (hardcoded degil); yollar script konumuna gore mutlak; DB yoksa sys.exit(1)
  (scheduler sessiz basari sanmasin); negatif --keep-days reddedilir; az once
  alinan yedek asla silinmez (en az 1 kopya garanti); dosya adi saniye
  hassasiyetinde + var olani ezmez; integrity_check + sqlite hata yakalama.
"""

import argparse
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

# Yollar script konumuna gore mutlak (SBK-007) — hangi cwd'den cagrilirsa dogru calissin
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_db_path() -> Path:
    """DATABASE_URL'den SQLite DB dosya yolunu turet (SBK-001)."""
    url = os.getenv("DATABASE_URL", "sqlite:///./data/financialos.db")
    if not url.startswith("sqlite:///"):
        raise SystemExit(f"backup.py yalnizca SQLite icindir; DATABASE_URL={url!r}")
    raw = url[len("sqlite:///"):]
    p = Path(raw)
    return p if p.is_absolute() else (_REPO_ROOT / raw).resolve()


DB_PATH    = _resolve_db_path()
BACKUP_DIR = _REPO_ROOT / "data" / "backups"


def backup(keep_days: int = 30) -> None:
    if keep_days < 0:
        raise SystemExit(f"HATA: --keep-days negatif olamaz (verilen: {keep_days}).")  # SBK-002

    if not DB_PATH.exists():
        raise SystemExit(f"HATA: DB bulunamadi: {DB_PATH}")  # SBK-001: hata koduyla cik

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # SBK-004: saniye hassasiyeti + var olani ezme
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    dest = BACKUP_DIR / f"{stamp}.db"
    _n = 1
    while dest.exists():
        dest = BACKUP_DIR / f"{stamp}-{_n}.db"
        _n += 1

    # Online backup + integrity_check + hata yakalama (SBK-005/006)
    src_conn = dest_conn = None
    try:
        src_conn = sqlite3.connect(DB_PATH)
        dest_conn = sqlite3.connect(dest)
        src_conn.backup(dest_conn)
        row = dest_conn.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise sqlite3.DatabaseError(f"integrity_check basarisiz: {row}")
    except sqlite3.Error as e:
        if dest_conn:
            dest_conn.close()
        if src_conn:
            src_conn.close()
        try:
            if dest.exists():
                dest.unlink()  # yarim/bozuk kopyayi temizle
        except OSError:
            pass
        raise SystemExit(f"HATA: yedekleme basarisiz: {e}")
    finally:
        if dest_conn:
            dest_conn.close()
        if src_conn:
            src_conn.close()

    size_kb = dest.stat().st_size // 1024
    print(f"Yedek alindi: {dest}  ({size_kb} KB)")

    # Eski yedekleri temizle — SBK-002/003: az once alinan `dest` ASLA silinmez (>=1 garanti)
    cutoff = time.time() - keep_days * 86400
    old_files = [
        f for f in BACKUP_DIR.glob("*.db")
        if f.resolve() != dest.resolve() and f.stat().st_mtime < cutoff
    ]
    for f in old_files:
        f.unlink()

    if old_files:
        print(f"{len(old_files)} eski yedek silindi (>{keep_days} gun).")
    else:
        print(f"Silinecek eski yedek yok (keep_days={keep_days}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinancialOS SQLite yedekleme")
    parser.add_argument(
        "--keep-days", type=int, default=30,
        help="Kac gunluk yedek saklansin (default: 30, negatif olamaz)"
    )
    args = parser.parse_args()
    backup(keep_days=args.keep_days)
