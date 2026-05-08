"""
Net Değer Backfill — 1 May 2026'dan bugüne günlük snapshot yazar.

Çalıştırma:
    python -m scripts.backfill_net_worth

Yöntem:
    - Bugün için generate_cockpit() (en doğru değer)
    - Geçmiş günler için: Account.balance'tan başla,
      target_date'ten sonraki transaction'ları ters uygula.
    - Investment: lot * güncel_fiyat (geçmiş fiyat kaydı yok → sabit yaklaşım)
    - Alacaklar: is_paid=False veya paid_date > target_date olanlar

NetWorthSnapshot tablosu create_all() ile oluşur.
Var olan snapshot'lar üzerine yazılır (upsert).
"""

import sys
import os

# Repo kökü Python path'ine ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    User, Account, AccountType, Transaction, TransactionType,
    PersonalDebt, DebtDirection, NetWorthSnapshot,
)
from app.rules_engine import generate_cockpit

START_DATE = date(2026, 5, 1)


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
            investment_value += (acc.lot_count or 0) * (acc.current_price or 0)

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


def main() -> None:
    db: Session = SessionLocal()
    try:
        user = db.query(User).order_by(User.id.asc()).first()
        if not user:
            print("HATA: Kullanıcı yok. python -m scripts.setup_data çalıştırın.")
            sys.exit(1)

        today = date.today()
        n = (today - START_DATE).days + 1
        print(f"Backfill başlıyor: {START_DATE} → {today} ({n} gün)\n")

        cur = START_DATE
        written = 0
        while cur <= today:
            snap = snapshot_for(db, user, cur)
            upsert(db, user.id, snap)
            print(
                f"  {cur}  Görülen={snap['net_worth_seen']:>12,.2f} TL  "
                f"Tam={snap['net_worth_full']:>12,.2f} TL"
            )
            cur += timedelta(days=1)
            written += 1

        print(f"\n✓ {written} snapshot yazıldı.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
