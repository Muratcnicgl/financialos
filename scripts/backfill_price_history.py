"""
PriceHistory Backfill — TEFAS'tan gunluk fiyat cekip price_history tablosuna yazar.

Kullanim:
    python -m scripts.backfill_price_history                          # tum investment hesaplari (emanet haric), son 365 gun
    python -m scripts.backfill_price_history --start 2025-05-09       # ozel baslangic
    python -m scripts.backfill_price_history --fund TLY               # tek fund
    python -m scripts.backfill_price_history --dry-run                # DB'ye yazmadan simule et

Yontem:
    - Account tablosundan account_type='investment' AND is_emanet not True olan hesaplarin fund_code'lari okunur
    - Her fund icin pytefas Crawler.fetch(start, end, fund_code=X, kind="YAT") tek cagri
      (paket icinde 28 gunluk chunk'lara bolunur, rate-limit otomatik yonetilir)
    - YAT bos donerse EMK fallback (fund_tracker.py patterni)
    - SQLite INSERT OR IGNORE (idempotent, kompozit PK)

Sektor patterni:
    - Default 1 yil (ADR-014: Sharesight/Portfolio Performance/Vanguard baseline)
    - Bulk upsert (SQLAlchemy 2.0 resmi sqlite_upsert + on_conflict_do_nothing)
    - Idempotent: tekrar calistirinca mevcut kayitlar atlanir

Kaynak: ADR-012 (PriceHistory schema), ADR-014 (1 yil default), fund_tracker.py
        (try_auto_fetch_fund_price patterni - YAT/EMK fallback).
"""

import sys
import os

# Repo koku Python path'ine ekle (backfill_net_worth.py patterni)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from app.database import SessionLocal, engine
from app.models import Account, AccountType, PriceHistory, PriceSource


SEPARATOR = "=" * 60


def _fetch_tefas_range(fund_code: str, start: date, end: date) -> list:
    """
    pytefas v0.3.0 ile fund_code icin start-end araliginda gunluk fiyat verisi cek.

    pytefas paketi otomatik:
    - 28 gunluk chunk'lara boler (TEFAS API 1 ay limiti)
    - Rate-limit (dakikada 6 istek) handle eder
    - Hafta sonu/tatil bos satir yerine atlar

    YAT bos donerse EMK fallback (fund_tracker.py try_auto_fetch_fund_price patterni).

    Returns: [{"date": date, "price": Decimal}, ...]
    """
    from pytefas import (  # noqa: PLC0415
        Crawler,
        TefasAPIError,
        TefasInvalidParameterError,
        TefasRateLimitError,
    )

    crawler = Crawler()

    def _fetch_kind(kind):
        try:
            df = crawler.fetch(
                start.isoformat(),
                end.isoformat(),
                kind=kind,
                fund_code=fund_code,
                columns="info",
            )
            return df
        except TefasInvalidParameterError as e:
            print("  [%s/%s] Gecersiz parametre: %s" % (fund_code, kind, e))
            return None
        except TefasRateLimitError as e:
            print("  [%s/%s] Rate limit (paket retry tukendi): %s" % (fund_code, kind, e))
            return None
        except TefasAPIError as e:
            print("  [%s/%s] API hatasi: %s" % (fund_code, kind, e))
            return None

    df = _fetch_kind("YAT")

    if df is None or df.empty:
        print("  [%s] YAT bos/hatali, EMK deneniyor..." % fund_code)
        df = _fetch_kind("EMK")

    if df is None or df.empty:
        return []

    rows = []
    for _, row in df.iterrows():
        # float -> str -> Decimal -> quantize(0.0001)
        # (BUG #007 + fund_tracker.py patterni, Numeric(19,4) ile uyumlu)
        price_decimal = Decimal(str(float(row["price"]))).quantize(Decimal("0.0001"))
        # pytefas v0.3.0 "date" kolonu dtype=object (str "YYYY-MM-DD") döner.
        # SQLite Date tipi Python date nesnesi ister, str reddeder.
        raw_date = row["date"]
        if isinstance(raw_date, str):
            price_date = date.fromisoformat(raw_date[:10])
        elif hasattr(raw_date, "date"):
            price_date = raw_date.date()
        else:
            price_date = raw_date
        rows.append({"date": price_date, "price": price_decimal})

    return rows


def backfill_fund(db, fund_code, start, end, dry_run):
    """Tek fund icin backfill. Bulk upsert + idempotent."""
    print("\n[%s] %s -> %s cekiliyor (pytefas otomatik chunk)..." % (fund_code, start, end))

    try:
        rows = _fetch_tefas_range(fund_code, start, end)
    except Exception as e:
        print("  HATA: TEFAS fetch basarisiz: %s: %s" % (type(e).__name__, e))
        return {"fetched": 0, "inserted": 0, "skipped": 0, "error": True}

    if not rows:
        print("  UYARI: Veri donmedi (fund_code yanlis veya tum aralik bos/tatil)")
        return {"fetched": 0, "inserted": 0, "skipped": 0, "error": False}

    print("  TEFAS dondu: %d satir" % len(rows))

    if dry_run:
        print("  DRY-RUN: DB'ye dokunulmadi. Gercek calistirmada %d satir denenir." % len(rows))
        return {"fetched": len(rows), "inserted": 0, "skipped": 0, "error": False}

    # Bulk insert: Core katmani (engine.connect) — ORM Session intercept'i bypass eder.
    # ORM Session + sqlite_upsert(ORM class).values(list) kombinasyonu Python-side
    # default'lari (fetched_at lambda) yanlis bind eder; Core + __table__ guvenli.
    values = [
        {
            "fund_code": fund_code,
            "price_date": r["date"],
            "source": PriceSource.TEFAS.value,  # Core insert: enum.value (str) gonder
            "close_price": r["price"],
        }
        for r in rows
    ]

    stmt = sqlite_upsert(PriceHistory.__table__).values(values)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["fund_code", "price_date", "source"]
    )
    with engine.connect() as conn:
        result = conn.execute(stmt)
        conn.commit()

    # SQLite: rowcount = gercekte eklenen satir sayisi (ignored olanlar dahil degil)
    inserted = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else 0
    skipped = len(rows) - inserted

    print("  Eklendi: %d  |  Atlandi (mevcut): %d" % (inserted, skipped))
    return {"fetched": len(rows), "inserted": inserted, "skipped": skipped, "error": False}


def main():
    parser = argparse.ArgumentParser(description="PriceHistory backfill (TEFAS)")
    parser.add_argument("--start", type=str, default=None,
                        help="YYYY-MM-DD (default: bugun - 365 gun)")
    parser.add_argument("--end", type=str, default=None,
                        help="YYYY-MM-DD (default: bugun)")
    parser.add_argument("--fund", type=str, default=None,
                        help="Tek fund kodu (default: tum investment hesaplari, emanet haric)")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB'ye yazma, sadece simule et")
    args = parser.parse_args()

    today = date.today()
    end_date = date.fromisoformat(args.end) if args.end else today
    start_date = date.fromisoformat(args.start) if args.start else (today - timedelta(days=365))

    if start_date > end_date:
        print("HATA: start (%s) > end (%s)" % (start_date, end_date))
        sys.exit(1)

    n_days = (end_date - start_date).days + 1
    print("Backfill: %s -> %s (%d gun)" % (start_date, end_date, n_days))
    if args.dry_run:
        print("MOD: DRY-RUN (DB'ye yazilmaz)")

    db = SessionLocal()
    try:
        if args.fund:
            fund_codes = [args.fund.upper()]
        else:
            # is_emanet NULL veya False olan investment hesaplari
            # (nullable kolon icin defansif filtre)
            accounts = (
                db.query(Account)
                .filter(Account.account_type == AccountType.investment)
                .filter(or_(Account.is_emanet == False, Account.is_emanet.is_(None)))  # noqa: E712
                .filter(Account.fund_code.isnot(None))
                .all()
            )
            fund_codes = sorted({a.fund_code.upper() for a in accounts if a.fund_code})

        if not fund_codes:
            print("HATA: Investment hesabi yok veya fund_code bos.")
            sys.exit(1)

        print("Fund'lar: %s" % ", ".join(fund_codes))

        totals = {"fetched": 0, "inserted": 0, "skipped": 0, "errors": 0}
        for fc in fund_codes:
            r = backfill_fund(db, fc, start_date, end_date, args.dry_run)
            totals["fetched"]  += r["fetched"]
            totals["inserted"] += r["inserted"]
            totals["skipped"]  += r["skipped"]
            if r["error"]:
                totals["errors"] += 1

        print("\n" + SEPARATOR)
        print("OZET: %d fund islendi" % len(fund_codes))
        print("  TEFAS'tan cekilen:  %d satir" % totals["fetched"])
        if not args.dry_run:
            print("  Yeni eklenen:       %d satir" % totals["inserted"])
            print("  Atlanan (mevcut):   %d satir (ON CONFLICT DO NOTHING)" % totals["skipped"])
        if totals["errors"]:
            print("  HATALI fund:        %d" % totals["errors"])
        if args.dry_run:
            print("  (DRY-RUN: hicbir sey yazilmadi)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
