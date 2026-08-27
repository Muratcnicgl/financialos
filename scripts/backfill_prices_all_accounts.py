r"""
Mevcut yatırım hesapları için geçmiş fiyat backfill (charter M4.5 / ADR-029).

Her aktif `investment` hesabının fund_code'u için verilen aralıktaki iş günlerinde TEFAS
fiyatını çeker ve PriceHistory'ye yazar (idempotent — ADR-012 kompozit PK; var olan gün
atlanır). Trend grafiği (net değer/fon performansı) için geçmiş veri sağlar.

Kullanım:  .\venv\Scripts\python.exe scripts/backfill_prices_all_accounts.py --days 30
           .\venv\Scripts\python.exe scripts/backfill_prices_all_accounts.py --start 2026-06-12 --end 2026-07-12
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Account, AccountType, PriceHistory, PriceSource  # noqa: E402


def _business_days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--start", type=str, default=None)
    ap.add_argument("--end", type=str, default=None)
    a = ap.parse_args()
    end = date.fromisoformat(a.end) if a.end else date.today()
    start = date.fromisoformat(a.start) if a.start else end - timedelta(days=a.days)

    from pytefas import Crawler
    crawler = Crawler()
    db = SessionLocal()
    added = 0
    try:
        fund_codes = {acc.fund_code for acc in db.query(Account).filter(
            Account.account_type == AccountType.investment, Account.fund_code.isnot(None)).all()}
        print(f"Fon kodlari: {sorted(fund_codes)} | {start} .. {end}")
        for fc in sorted(fund_codes):
            for d in _business_days(start, end):
                exists = db.query(PriceHistory).filter(
                    PriceHistory.fund_code == fc, PriceHistory.price_date == d,
                    PriceHistory.source == PriceSource.TEFAS.value).first()
                if exists:
                    continue
                try:
                    df = crawler.fetch(d.isoformat(), kind="YAT", fund_code=fc, columns="info")
                    if df is not None and not df.empty:
                        price = Decimal(str(float(df.iloc[0]["price"]))).quantize(Decimal("0.0001"))
                        db.add(PriceHistory(fund_code=fc, price_date=d,
                                            source=PriceSource.TEFAS.value, close_price=price))
                        db.commit()
                        added += 1
                except Exception as e:  # rate-limit/boş gün → atla
                    if "RateLimit" in type(e).__name__:
                        time.sleep(2)
                    continue
        print(f"OK: {added} yeni fiyat noktasi eklendi ({len(fund_codes)} fon).")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
