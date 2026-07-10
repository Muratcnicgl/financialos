"""
BUG #103 — karta gelen gelir (iade/cashback) kart borcunu AZALTIR.
Executor + simülasyon birebir. Nakit/yatırıma gelen gelir varlığı artırır (kontrol).
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType
from app.action_executor import _execute_add_transaction
from app.simulation_engine import _apply_action, AccountSnap, WorldSnap


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


def test_executor_karta_iade_borcu_azaltir(db):
    card = Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                   balance=5000.0, credit_limit=12000.0)
    db.add(card)
    db.commit()
    db.refresh(card)
    _execute_add_transaction(db, 1, {
        "transaction_type": "income", "amount": 200.0, "account_id": card.id,
        "auto_update_balance": True, "category": "iade",
    })
    db.refresh(card)
    assert card.balance == 4800.0  # borç azaldı


def test_executor_nakite_gelir_artirir(db):
    cash = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=1000.0)
    db.add(cash)
    db.commit()
    db.refresh(cash)
    _execute_add_transaction(db, 1, {
        "transaction_type": "income", "amount": 200.0, "account_id": cash.id,
        "auto_update_balance": True,
    })
    db.refresh(cash)
    assert cash.balance == 1200.0


def test_sim_karta_iade_borcu_azaltir():
    card = AccountSnap(id=2, name="Ziraat", account_type="credit_card", balance=5000.0)
    world = WorldSnap(as_of=date(2026, 5, 1), accounts=[card], incomes=[], debts=[])
    ok, _ = _apply_action(world, "add_transaction", {
        "account_id": 2, "amount": 200.0, "transaction_type": "income",
        "auto_update_balance": True,
    })
    assert ok is True
    assert world.acc(2).balance == 4800.0
