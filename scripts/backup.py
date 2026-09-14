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
import sys
from pathlib import Path

# BUG #494 (DEVOPS-010): çekirdek `app/yedek.py`de — uygulama scheduler'ı da aynı kodu koşturur.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.yedek import YedekHatasi, sqlite_db_yolu, sqlite_yedekle, varsayilan_yedek_dizini  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = varsayilan_yedek_dizini()


def backup(keep_days: int = 30) -> None:
    try:
        dest, silinen = sqlite_yedekle(sqlite_db_yolu(), BACKUP_DIR, keep_days)
    except YedekHatasi as e:
        raise SystemExit(f"HATA: {e}") from e  # SBK-001/002/005: hata koduyla çık
    size_kb = dest.stat().st_size // 1024
    print(f"Yedek alindi: {dest}  ({size_kb} KB)")
    if silinen:
        print(f"{silinen} eski yedek silindi (>{keep_days} gun).")
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
