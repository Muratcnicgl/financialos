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


def test_kredi_taksiti_burn_e_dahil(db):
    """
    BUG #124: gelirsiz senaryoda kredi taksitleri de cash'i eritir → runway kısalır.
    nakit 6000, harcama 600/30g (=20/gün) + kredi 9000/ay (=300/gün) → burn 320/gün → ~18 gün.
    (Taksit hariç olsaydı 300 gün çıkıp crunch ile çelişirdi.)
    """
    from app.models import Account, AccountType
    db.add(Account(user_id=1, name="K1", account_type=AccountType.loan,
                   balance=30000.0, monthly_payment=5000.0, remaining_installments=6))
    db.add(Account(user_id=1, name="K2", account_type=AccountType.loan,
                   balance=20000.0, monthly_payment=4000.0, remaining_installments=5))
    _exp(db, 600.0, TODAY - timedelta(days=5))
    db.commit()
    runway = _calculate_cash_runway(1, TODAY, db, nakit=6000.0)
    assert runway == 18                          # 6000 / (20 + 300) = 18.75 → 18


def test_bitmis_kredi_burn_e_dahil_degil(db):
    """remaining_installments=0 kredi taksiti artık ödenmiyor → burn'e dahil olmaz."""
    from app.models import Account, AccountType
    db.add(Account(user_id=1, name="Bitmis", account_type=AccountType.loan,
                   balance=0.0, monthly_payment=5000.0, remaining_installments=0))
    _exp(db, 3000.0, TODAY - timedelta(days=5))
    db.commit()
    # sadece harcama: 3000/30=100/gün → 3000 nakit / 100 = 30 gün (kredi sayılmaz)
    assert _calculate_cash_runway(1, TODAY, db, nakit=3000.0) == 30


def test_cockpit_alani(db):
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=3000.0))
    _exp(db, 1500.0, TODAY - timedelta(days=10))
    db.commit()
    cockpit = generate_cockpit(1, TODAY, db)
    assert "nakit_runway_gun" in cockpit
    # nakit 3000, burn 1500/30=50 → 60 gün
    assert cockpit["nakit_runway_gun"] == 60
