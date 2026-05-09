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

import argparse
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import desc, case
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    User, Account, AccountType, Transaction, TransactionType,
    PersonalDebt, DebtDirection, NetWorthSnapshot,
    PriceHistory, PriceSource,
)
from app.rules_engine import generate_cockpit

START_DATE = date(2026, 5, 1)


def _get_price_at(db: Session, fund_code: str, target_date: date) -> Optional[Decimal]:
    """Forward-fill: target_date'te veya oncesinde en yakin fiyat.
    Source priority: manual > tefas > yfinance > isyatirim.
    Hafta sonu/tatil icin en yakin onceki is gunu fiyati doner.
    Hic fiyat yoksa None."""
    if not fund_code:
        return None

    source_order = case(
        (PriceHistory.source == PriceSource.MANUAL, 1),
        (PriceHistory.source == PriceSource.TEFAS, 2),
        (PriceHistory.source == PriceSource.YFINANCE, 3),
        (PriceHistory.source == PriceSource.ISYATIRIM, 4),
        else_=99,
    )

    row = (
        db.query(PriceHistory)
        .filter(PriceHistory.fund_code == fund_code)
        .filter(PriceHistory.price_date <= target_date)
        .order_by(desc(PriceHistory.price_date), source_order)
        .first()
    )

    return row.close_price if row else None


def _account_inception_at(account) -> Optional[date]:
    """Account inception proxy. Su an account.created_at.date() -
    Account.purchased_date alani yok. Wave-3'te InvestmentTransaction.first()
    tarihi kullanilacak (ADR-015)."""
    if not account.created_at:
        return None
    return account.created_at.date()


def _investment_value_at(db: Session, account, target_date: date) -> float:
    """target_date icin yatirim hesabi degeri.

    Mantik (ADR-015):
    1. Account o tarihte var miydi? (inception kontrolu)
    2. Gecmis fiyat? (price_history forward-fill)
    3. Yoksa cost_per_lot fallback
    4. lot_count: bugunku deger (Wave-2 sabit varsayim)
    """
    inception = _account_inception_at(account)
    if inception and target_date < inception:
        return 0.0

    lot = account.lot_count or 0
    if lot == 0:
        return 0.0

    price = _get_price_at(db, account.fund_code, target_date)

    if price is None:
        if account.cost_per_lot:
            return float(lot) * float(account.cost_per_lot)
        return 0.0

    return float(lot) * float(price)


def _balance_at(db: Session, account: Account, target_date: date) -> float:
    """Account.balance'ı target_date için geriye doğru rekonstürükte et."""
    after = db.query(Transaction).filter(
        Transaction.account_id == account.id,
        Transaction.transaction_date > target_date,
    ).all()

    bal = account.balance
    for t in after:
        if t.transaction_type == TransactionType.income:
            bal -= t.amount   # undo: income +bakiye → geri al
        elif t.transaction_type == TransactionType.expense:
            bal += t.amount   # undo: expense -bakiye → geri al
    return bal


def _receivables_at(db: Session, user_id: int, target_date: date) -> float:
    """target_date itibariyle ödenmemiş alacakların toplamı."""
    rows = (
        db.query(PersonalDebt)
        .filter(
            PersonalDebt.user_id == user_id,
            PersonalDebt.direction == DebtDirection.receivable,
        )
        .filter(
            (PersonalDebt.is_paid == False) |       # noqa: E712
            (PersonalDebt.paid_date > target_date)
        )
        .all()
    )
    return sum(r.amount for r in rows)


def snapshot_for(db: Session, user: User, target_date: date) -> dict:
    """target_date için net değer snapshot dict'i üret."""
    today = date.today()

    if target_date >= today:
        cockpit = generate_cockpit(user.id, today, db)
        recv = max(0.0, cockpit.get("net_deger_tam", cockpit["net_deger"]) - cockpit["net_deger"])
        return dict(
            snapshot_date=today,
            net_worth_seen=cockpit["net_deger"],
            net_worth_full=cockpit.get("net_deger_tam", cockpit["net_deger"]),
            cash=cockpit["nakit_kasa"],
            card_debt=cockpit["kart_borcu"],
            loan_debt=cockpit["kredi_borcu"],
            investment_value=cockpit["yatirim_deger"],
            receivables=recv,
        )

    accounts = db.query(Account).filter(Account.user_id == user.id).all()
    cash = card_debt = loan_debt = investment_value = 0.0

    for acc in accounts:
        bal = _balance_at(db, acc, target_date)
        if acc.account_type == AccountType.cash:
            cash += bal
        elif acc.account_type == AccountType.credit_card:
            card_debt += bal
        elif acc.account_type == AccountType.loan:
            loan_debt += bal
        elif acc.account_type == AccountType.investment and not acc.is_emanet:
            investment_value += _investment_value_at(db, acc, target_date)

    receivables = _receivables_at(db, user.id, target_date)
    seen = round(cash + investment_value - card_debt - loan_debt, 2)
    full = round(seen + receivables, 2)

    return dict(
        snapshot_date=target_date,
        net_worth_seen=seen,
        net_worth_full=full,
        cash=round(cash, 2),
        card_debt=round(card_debt, 2),
        loan_debt=round(loan_debt, 2),
        investment_value=round(investment_value, 2),
        receivables=round(receivables, 2),
    )


def upsert(db: Session, user_id: int, snap: dict) -> None:
    existing = (
        db.query(NetWorthSnapshot)
        .filter_by(user_id=user_id, snapshot_date=snap["snapshot_date"])
        .first()
    )
    if existing:
        for k, v in snap.items():
            setattr(existing, k, v)
    else:
        db.add(NetWorthSnapshot(user_id=user_id, **snap))
    db.commit()


def run_backfill(start_date: date, end_date: date, verbose: bool = True) -> int:
    """NetWorthSnapshot'lari start_date -> end_date araliginda yazar.

    Idempotent (upsert pattern). Kullanim:
    - CLI: python -m scripts.backfill_net_worth (main() bunu cagirir)
    - Programatic: from scripts.backfill_net_worth import run_backfill

    Returns: yazilan snapshot sayisi.
    """
    if start_date > end_date:
        if verbose:
            print(f"HATA: start ({start_date}) > end ({end_date})")
        return 0

    db: Session = SessionLocal()
    try:
        user = db.query(User).order_by(User.id.asc()).first()
        if not user:
            if verbose:
                print("HATA: Kullanici yok. python -m scripts.setup_data calistirin.")
            return 0

        n = (end_date - start_date).days + 1
        if verbose:
            print(f"Backfill basliyor: {start_date} -> {end_date} ({n} gun)\n")

        cur = start_date
        written = 0
        while cur <= end_date:
            snap = snapshot_for(db, user, cur)
            upsert(db, user.id, snap)
            if verbose:
                print(
                    f"  {cur}  Gorulen={snap['net_worth_seen']:>12,.2f} TL  "
                    f"Tam={snap['net_worth_full']:>12,.2f} TL  "
                    f"Yatirim={snap['investment_value']:>10,.2f}"
                )
            cur += timedelta(days=1)
            written += 1

        if verbose:
            print(f"\nTamam: {written} snapshot yazildi.")
        return written
    finally:
        db.close()


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
