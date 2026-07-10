"""
BUG #102 — kısmi satış sonrası yatırım değeri tutarlılığı.
Satış actual_price ile yapılınca kalan_deger = kalan_lot*actual_price. current_price de
güncellenmezse balance ile lot_count*current_price (cockpit) ve simülasyon (balance okur)
birbirinden sapar. Fix: current_price = actual_price → hepsi tutarlı.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType
from app.action_executor import _execute_sell_investment


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    u = User(id=1, name="murat")
    s.add(u)
    s.commit()
    yield s
    s.close()


def _seed(db):
    inv = Account(user_id=1, name="TLY Fon", account_type=AccountType.investment,
                  lot_count=10, cost_per_lot=100.0, current_price=100.0, balance=1000.0,
                  is_emanet=False)
    cash = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=0.0)
    db.add_all([inv, cash])
    db.commit()
    db.refresh(inv)
    db.refresh(cash)
    return inv, cash


def test_satis_sonrasi_balance_current_price_tutarli(db):
    inv, cash = _seed(db)
    # 4 lotu piyasa fiyatı 120'den sat (actual_price != eski current_price 100)
    res = _execute_sell_investment(db, 1, {
        "investment_id": inv.id, "lots_to_sell": 4, "actual_price": 120.0,
        "credit_to_account_id": cash.id,
    })
    assert res["success"] is True
    db.refresh(inv)
    # kalan 6 lot; current_price taze piyasa (120) olmalı → balance == 6*120
    assert inv.lot_count == 6
    assert inv.current_price == 120.0
    assert inv.balance == pytest.approx(6 * 120.0)
    # tutarlılık: balance == lot_count * current_price (cockpit/sim ile uyumlu)
    assert inv.balance == pytest.approx(inv.lot_count * inv.current_price)
