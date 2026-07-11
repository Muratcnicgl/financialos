"""
FEAT-010 — nakit runway (gelirsiz mevcut nakit kaç gün yeter).
runway = nakit / (son 30g gider / 30). Startup runway kavramı. Deterministik izole DB.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, Transaction, TransactionType
from app.rules_engine import _calculate_cash_runway, generate_cockpit

TODAY = date(2026, 6, 1)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


def _exp(db, amount, when):
    db.add(Transaction(user_id=1, transaction_type=TransactionType.expense,
                       amount=amount, category="market", transaction_date=when))
    db.commit()


def test_runway_hesap(db):
    # nakit 3000, son 30g gider 3000 → günlük burn 100 → runway 30 gün
    _exp(db, 3000.0, TODAY - timedelta(days=10))
    runway = _calculate_cash_runway(1, TODAY, db, nakit=3000.0)
    assert runway == 30


def test_nakit_sifir_runway_sifir(db):
    _exp(db, 500.0, TODAY - timedelta(days=5))
    assert _calculate_cash_runway(1, TODAY, db, nakit=0.0) == 0


def test_harcama_yoksa_belirsiz(db):
    # son 30g hiç gider yok → None (belirsiz/sonsuz)
    assert _calculate_cash_runway(1, TODAY, db, nakit=5000.0) is None


def test_pencere_disi_gider_sayilmaz(db):
    # 40 gün önceki gider pencere dışı → sayılmaz → belirsiz
    _exp(db, 3000.0, TODAY - timedelta(days=40))
    assert _calculate_cash_runway(1, TODAY, db, nakit=3000.0) is None


def test_cockpit_alani(db):
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=3000.0))
    _exp(db, 1500.0, TODAY - timedelta(days=10))
    db.commit()
    cockpit = generate_cockpit(1, TODAY, db)
    assert "nakit_runway_gun" in cockpit
    # nakit 3000, burn 1500/30=50 → 60 gün
    assert cockpit["nakit_runway_gun"] == 60
