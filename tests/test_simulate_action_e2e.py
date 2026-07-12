"""
simulate_action uçtan uca — "3-Ufuklu Karar Masası" çekirdeği.
Endpoint testleri simulate_action'ı MOCK'luyordu → çekirdek mantık (world yükle → aksiyon
uygula → projekte et → snapshot/delta) hiç entegrasyon-test edilmiyordu. Deterministik base_date.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType
from app.simulation_engine import simulate_action


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


def _cash(db, balance=5000.0):
    a = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=balance)
    db.add(a); db.commit(); db.refresh(a)
    return a


def test_simulate_add_transaction_expense_3_ufuk(db):
    cash = _cash(db, 5000.0)
    res = simulate_action(
        db, 1, "add_transaction",
        {"transaction_type": "expense", "amount": 1000.0, "account_id": cash.id,
         "auto_update_balance": True, "category": "market"},
        horizons_days=(0, 30, 90), base_date=date(2026, 5, 1),
    )
    assert res["ok"] is True
    snaps = res["snapshots"]
    labels = [s["label"] for s in snaps]
    assert labels == ["T+0", "T+30", "T+90"]
    # T+0'da nakit 1000 azalmış olmalı
    t0 = snaps[0]
    assert t0["nakit_kasa"] == 4000.0
    # baseline (aksiyonsuz) ile delta var
    assert "delta_vs_baseline" in t0
    assert "comparison" in res


def test_simulate_sell_investment_lot_azalir_nakit_artar(db):
    cash = _cash(db, 0.0)
    inv = Account(user_id=1, name="TLY", account_type=AccountType.investment,
                  lot_count=10.0, cost_per_lot=800.0, current_price=1000.0, balance=10000.0)
    db.add(inv); db.commit(); db.refresh(inv)

    res = simulate_action(
        db, 1, "sell_investment",
        {"investment_id": inv.id, "lots_to_sell": 4.0, "actual_price": 1000.0,
         "credit_to_account_id": cash.id},
        horizons_days=(0, 30), base_date=date(2026, 5, 1),
    )
    assert res["ok"] is True
    t0 = res["snapshots"][0]
    # kalan 6 lot * 1000 = 6000 yatırım; nakit satıştan artmış (stopaj sonrası)
    assert t0["yatirim_deger"] == 6000.0
    assert t0["nakit_kasa"] > 0


def test_simulate_emanet_satis_ok_false(db):
    """Emanet satışı simülasyonda da reddedilir (MC1) — ok=False, snapshot yok."""
    _cash(db, 0.0)
    emanet = Account(user_id=1, name="Altın Emanet", account_type=AccountType.investment,
                     lot_count=5.0, cost_per_lot=1000.0, current_price=1200.0,
                     balance=6000.0, is_emanet=True)
    db.add(emanet); db.commit(); db.refresh(emanet)

    res = simulate_action(
        db, 1, "sell_investment",
        {"investment_id": emanet.id, "lots_to_sell": 2.0, "credit_to_account_id": 1},
        horizons_days=(0, 30), base_date=date(2026, 5, 1),
    )
    assert res["ok"] is False
    assert res["snapshots"] == []
