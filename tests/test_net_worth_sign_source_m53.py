"""
M53 (Wave-7) — net-worth işaret konvansiyonu TEK KAYNAK (SBN-001 + BUG #161 ailesi).

İşaretin hesap-tipine bağlı olması artık `app/balance_rules.balance_delta` tek yerinde. Bu test:
1. balance_delta işaret birimleri (cash/credit_card/loan × income/expense).
2. SBN-001 regresyon: _balance_at kredi kartı geçmişini TİP-FARKINDA rekonstürükte eder (eski agnostik bug yok).
3. GATE: gerçek kredi+kart+hesap verisiyle net-worth = elle hesap, iki dialect'te (SQLite + Postgres) aynı.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.balance_rules import balance_delta, net_worth_seen
from app.models import Base, User, Account, AccountType, Transaction, TransactionType, RecurringIncome
from app.rules_engine import generate_cockpit
from tests.pg_gate import postgres_url_or_skip, fresh_pg_database

TODAY = date(2026, 7, 18)


# ---- 1. balance_delta işaret birimleri ----
@pytest.mark.parametrize("atype,ttype,expected", [
    ("cash", "income", Decimal("100")),
    ("cash", "expense", Decimal("-100")),
    ("credit_card", "expense", Decimal("100")),    # harcama borcu ARTIRIR
    ("credit_card", "income", Decimal("-100")),    # ödeme borcu azaltır
    ("loan", "expense", Decimal("-100")),          # taksit borcu azaltır
    ("loan", "income", Decimal("0")),              # tanımsız → 0
    ("investment", "income", Decimal("0")),        # bakiye tx ile değişmez
])
def test_balance_delta_isaret(atype, ttype, expected):
    assert balance_delta(atype, ttype, 100) == expected


# ---- 2. SBN-001 regresyon: kredi kartı geçmişi tip-farkında ----
def test_sbn001_kredi_karti_gecmis_dogru():
    """Kart bakiyesi 5000 (borç). 3 gün sonra 500 harcama (borç 5500'e çıkmıştı). Harcamadan
    ÖNCEki gün için _balance_at → 5000 (harcamanın eklediği 500 geri alınır). Eski agnostik kod
    expense'i +500 undo edip 5500 verirdi (SBN-001)."""
    from scripts.backfill_net_worth import _balance_at
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng); db = sessionmaker(bind=eng)()
    try:
        u = User(id=1, name="m", email="m@x.com"); db.add(u); db.commit()
        kart = Account(user_id=1, name="Kart", account_type=AccountType.credit_card, balance=Decimal("5500"))
        db.add(kart); db.commit()
        # 3 gün ÖNCE 500 harcama (bu borç 5000→5500 yapmıştı)
        db.add(Transaction(user_id=1, account_id=kart.id, transaction_type=TransactionType.expense,
                           amount=Decimal("500"), transaction_date=date(2026, 7, 15)))
        db.commit()
        # 14 Tem (harcamadan önce) → borç 5000 olmalı (5500 - harcamanın eklediği 500)
        bal = _balance_at(db, kart, date(2026, 7, 14))
        assert round(bal, 2) == 5000.00, f"SBN-001: kredi kartı geçmişi yanlış — {bal} (5000 bekleniyordu)"
    finally:
        db.close(); eng.dispose()


# ---- 3. GATE: net-worth elle-hesap, iki dialect ----
def _seed_networth(url, **kw):
    eng = create_engine(url, **kw); Base.metadata.create_all(eng); db = sessionmaker(bind=eng)()
    try:
        u = User(id=1, name="murat", email="m@x.com"); db.add(u); db.commit()
        db.add_all([
            Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=Decimal("9747.95"), is_emanet=False),
            Account(user_id=1, name="Kart", account_type=AccountType.credit_card, balance=Decimal("10180.01"), is_emanet=False),
            Account(user_id=1, name="Kredi1", account_type=AccountType.loan, balance=Decimal("20549.00"), is_emanet=False),
            Account(user_id=1, name="Kredi2", account_type=AccountType.loan, balance=Decimal("65933.42"), is_emanet=False),
            Account(user_id=1, name="TLY", account_type=AccountType.investment, lot_count=10, current_price=Decimal("100"), is_emanet=False),
        ])
        db.commit()
        c = generate_cockpit(1, TODAY, db)
        return Decimal(str(c["net_deger"]))
    finally:
        db.close(); eng.dispose()


def test_net_worth_elle_hesap_iki_dialect():
    # elle: nakit 9747.95 + yatırım 1000 (10*100) − kart 10180.01 − kredi (20549+65933.42) = -85914.48
    manual = net_worth_seen(Decimal("9747.95"), Decimal("1000"), Decimal("10180.01"), Decimal("86482.42"))
    assert manual == Decimal("-85914.48")
    sqlite_nw = _seed_networth("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    assert sqlite_nw == Decimal("-85914.48"), f"SQLite net-worth elle-hesapla uyuşmuyor: {sqlite_nw}"
    # iki dialect: Postgres de aynı (varsa)
    pg = fresh_pg_database(postgres_url_or_skip(), "fos_networth")
    pg_nw = _seed_networth(pg)
    assert pg_nw == sqlite_nw, f"net-worth dialect farkı: SQLite={sqlite_nw} Postgres={pg_nw}"
