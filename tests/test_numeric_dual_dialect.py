"""
M52 (Wave-7) — Numeric/tip bütünlüğü iki dialect'te (B4).

GATE: aynı finansal işlem dizisi SQLite + Postgres'te **bit-bire aynı Decimal** üretmeli. Postgres yoksa SKIP.

R3 bulgusu (M52): SQLite gerçek DECIMAL tipine sahip DEĞİL (Numeric'i REAL/double saklar). GERÇEKÇİ TL
büyüklüklerinde (<~1 trilyon, double ~15-16 anlamlı hane) SQLite SQL-sum'ı Postgres NUMERIC(19,4) ile
kuruşuna kadar AYNI. Yalnız absürt değerlerde (19-hane limitine yakın) veya çok-terimli float-aggregation'da
SQLite sapar → belgelenmiş dialect-divergence (dev SQLite gerçekçi veri, prod Postgres exact).

Bu test app'in SQL-sum yollarını (goal_engine baseline, interest_leak) Murat'ın GERÇEK büyüklükleriyle
iki dialect'te karşılaştırır — domain-anlamlı bütünlük kanıtı.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, RecurringIncome, Transaction, TransactionType
from app.goal_engine import calculate_baseline_for_debt_freedom
from app.rules_engine import calculate_interest_leak, calculate_envelopes
from tests.pg_gate import postgres_url_or_skip, fresh_pg_database

from datetime import date

# Murat'ın gerçek Mayıs/Temmuz 2026 büyüklükleri (kuruş hassasiyetli)
_SEED = [
    ("Enpara Nakit", AccountType.cash, Decimal("9747.95"), None),
    ("Ziraat Kart", AccountType.credit_card, Decimal("10180.01"), 4.25),
    ("Garanti Kredi 1", AccountType.loan, Decimal("20549.00"), 3.0),
    ("Garanti Kredi 2", AccountType.loan, Decimal("65933.42"), 2.5),
]
TODAY = date(2026, 7, 18)


def _seed_and_compute(url: str, **kw) -> dict:
    eng = create_engine(url, **kw)
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    try:
        u = User(id=1, name="murat", email="m@x.com"); db.add(u); db.commit()
        for name, atype, bal, rate in _SEED:
            db.add(Account(user_id=u.id, name=name, account_type=atype, balance=bal, interest_rate=rate))
        # bu ayki giderler (SQL-sum yolu: envelopes/month_aggregates)
        for i in range(20):
            db.add(Transaction(user_id=u.id, transaction_type=TransactionType.expense,
                               amount=Decimal("100.10") + Decimal(i), category="market",
                               description="m", transaction_date=TODAY))
        db.commit()
        # SQL-sum tabanlı hesaplar
        baseline = calculate_baseline_for_debt_freedom(u.id, db)          # sum(loan+card balances)
        leak = calculate_interest_leak(u.id, db)                          # borç*oran (Python) ama borç DB'den
        # envelope harcanan: SQL sum(Transaction.amount)
        from app.models import Envelope
        db.add(Envelope(user_id=u.id, category="market", monthly_amount=Decimal("1000"), is_active=True)); db.commit()
        env = calculate_envelopes(u.id, TODAY, db)
        return {
            "baseline": baseline,
            "aylik_faiz_toplam": Decimal(str(leak["aylik_toplam"])),
            "envelope_harcanan": Decimal(str(env["toplam_harcanan"])),
        }
    finally:
        db.close(); eng.dispose()


def test_numeric_iki_dialect_bit_bire_ayni():
    pg_url = fresh_pg_database(postgres_url_or_skip(), "fos_numeric")
    sqlite_res = _seed_and_compute("sqlite:///:memory:",
                                   connect_args={"check_same_thread": False}, poolclass=StaticPool)
    pg_res = _seed_and_compute(pg_url)
    for key in ("baseline", "aylik_faiz_toplam", "envelope_harcanan"):
        assert sqlite_res[key] == pg_res[key], (
            f"{key} dialect'ler arasında FARKLI: SQLite={sqlite_res[key]} Postgres={pg_res[key]}")
    # baseline = 10180.01 + 20549.00 + 65933.42 = 96662.43 (kart+kredi)
    assert sqlite_res["baseline"] == Decimal("96662.43")


def test_sqlite_numeric_siniri_belgelenmis():
    """R3 belgelenmiş divergence: SQLite 19-hane limitine yakın absürt değerde REAL-drift eder,
    Postgres exact. Gerçekçi TL'de (bu sınırın çok altında) sorun YOK — üstteki test kanıtlar."""
    from sqlalchemy import Column, Integer, Numeric, MetaData, Table, insert, select
    md = MetaData()
    absurd = Decimal("9999999999999.9999")  # ~10 trilyon TL — gerçekçi değil
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    t = Table("m", md, Column("id", Integer, primary_key=True), Column("v", Numeric(19, 4)))
    md.create_all(e)
    with e.begin() as c:
        c.execute(insert(t).values(id=1, v=absurd))
    with e.connect() as c:
        got = c.execute(select(t.c.v)).scalar()
    e.dispose()
    # SQLite bu absürt değeri exact TUTAMAZ (double precision) — bu bilinen/belgelenmiş sınır.
    assert got != absurd  # SQLite drift eder (dev-only, gerçekçi veri etkilenmez; prod Postgres exact)
