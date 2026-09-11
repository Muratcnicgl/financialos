"""
Net Değer Backfill — 1 May 2026'dan bugüne günlük snapshot yazar.

Çalıştırma:
    python -m scripts.backfill_net_worth

Yöntem:
    - Bugün için generate_cockpit() (en doğru değer)
    - Geçmiş günler için: Account.balance'tan başla,
      target_date'ten sonraki transaction'ları ters uygula.
    - Investment: lot * gecmis_fiyat (price_history forward-fill, ADR-015)
    - Alacaklar: is_paid=False veya paid_date > target_date olanlar

NetWorthSnapshot tablosu create_all() ile oluşur.
Var olan snapshot'lar üzerine yazılır (upsert).
"""

import sys
import os

# Repo kökü Python path'ine ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys
import os

# Repo kökü Python path'ine ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from datetime import date

# BUG #401 (BE-033): hesaplama `app/services/net_worth_backfill.py`de — uygulama çalışma
# zamanı artık scripts/ paketine bağımlı değil. Eski adlar burada yeniden dışa aktarılır
# (testler ve elle kullanım için).
from app.services.net_worth_backfill import (  # noqa: F401
    START_DATE, run_backfill, snapshot_for, upsert,
    _balance_at, _investment_value_at, _receivables_at, _get_price_at, _account_inception_at,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="NetWorthSnapshot backfill")
    parser.add_argument("--start", type=str, default=None,
                        help=f"YYYY-MM-DD (default: {START_DATE})")
    parser.add_argument("--end", type=str, default=None,
                        help="YYYY-MM-DD (default: bugun)")
    args = parser.parse_args()

    today = date.today()
    start_date = date.fromisoformat(args.start) if args.start else START_DATE
    end_date = date.fromisoformat(args.end) if args.end else today

    n = run_backfill(start_date, end_date, verbose=True)
    if n == 0 and start_date > end_date:
        sys.exit(1)


if __name__ == "__main__":
    main()
