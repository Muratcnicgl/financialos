"""
simulate_action — update_account_balance / mark_debt_paid / update_fund_price kolları.
Bu üç sim aksiyonu (RAM üzerinde önizleme) test edilmemişti. Özellikle mark_debt_paid'in
NAKİT hareketi gerçek executor (action_executor #113) ile TUTARLI olmalı: alacak → nakit +=,
borç → nakit -=. Emanet bakiye değişimi MC1 gereği simülasyonda da bloklanmalı.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, PersonalDebt, DebtDirection
from app.simulation_engine import simulate_action

BASE = date(2026, 5, 1)


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


# ---- update_account_balance ------------------------------------------------

def test_sim_update_account_balance(db):
    cash = _cash(db, 5000.0)
    res = simulate_action(db, 1, "update_account_balance",
                          {"account_id": cash.id, "new_balance": 8000.0},
                          horizons_days=(0,), base_date=BASE)
    assert res["ok"] is True
    assert res["snapshots"][0]["nakit_kasa"] == 8000.0


def test_sim_update_account_balance_emanet_bloklu(db):
    _cash(db, 0.0)
    emanet = Account(user_id=1, name="Altın Emanet", account_type=AccountType.investment,
                     lot_count=5.0, current_price=1200.0, balance=6000.0, is_emanet=True)
    db.add(emanet); db.commit(); db.refresh(emanet)
    res = simulate_action(db, 1, "update_account_balance",
                          {"account_id": emanet.id, "new_balance": 1.0},
                          horizons_days=(0,), base_date=BASE)
    assert res["ok"] is False           # MC1 emanet guard
    assert res["snapshots"] == []


# ---- mark_debt_paid (nakit hareketi #113 ile tutarlı) ----------------------

def test_sim_mark_receivable_paid_nakit_artar(db):
    cash = _cash(db, 1000.0)
    d = PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                     amount=2000.0, is_paid=False)
    db.add(d); db.commit(); db.refresh(d)

    res = simulate_action(db, 1, "mark_debt_paid", {"debt_id": d.id},
                          horizons_days=(0,), base_date=BASE)
    assert res["ok"] is True
    # alacak tahsil → nakit 1000 + 2000 = 3000
    assert res["snapshots"][0]["nakit_kasa"] == 3000.0


def test_sim_mark_payable_paid_nakit_azalir(db):
    cash = _cash(db, 5000.0)
    d = PersonalDebt(user_id=1, counterparty="Kirveci", direction=DebtDirection.payable,
                     amount=1500.0, is_paid=False)
    db.add(d); db.commit(); db.refresh(d)

    res = simulate_action(db, 1, "mark_debt_paid", {"debt_id": d.id},
                          horizons_days=(0,), base_date=BASE)
    assert res["ok"] is True
    # borç öde → nakit 5000 - 1500 = 3500
    assert res["snapshots"][0]["nakit_kasa"] == 3500.0


def test_sim_mark_debt_paid_bulunamayan_id(db):
    _cash(db, 1000.0)
    res = simulate_action(db, 1, "mark_debt_paid", {"debt_id": 9999},
                          horizons_days=(0,), base_date=BASE)
    assert res["ok"] is False


# ---- update_fund_price -----------------------------------------------------

def test_sim_update_fund_price_yeniden_degerleme(db):
    inv = Account(user_id=1, name="TLY", account_type=AccountType.investment,
                  lot_count=10.0, cost_per_lot=800.0, current_price=1000.0, balance=10000.0)
    db.add(inv); db.commit(); db.refresh(inv)

    res = simulate_action(db, 1, "update_fund_price",
                          {"account_id": inv.id, "new_price": 1200.0},
                          horizons_days=(0,), base_date=BASE)
    assert res["ok"] is True
    # 10 lot * 1200 = 12000
    assert res["snapshots"][0]["yatirim_deger"] == 12000.0


def test_sim_desteklenmeyen_aksiyon(db):
    _cash(db, 1000.0)
    res = simulate_action(db, 1, "teleport_money", {},
                          horizons_days=(0,), base_date=BASE)
    assert res["ok"] is False


def test_sim_projeksiyonda_payable_vadesinde_nakitten_duser(db):
    """
    İleri projeksiyon (T+30): vadesi ufuk içinde olan ÖDENMEMİŞ borç, nakitten düşülür
    (branch 427-428 — sınır testinde alacak kolu vardı, borç kolu yoktu; işaret kilidi).
    """
    from datetime import timedelta
    cash = _cash(db, 10000.0)
    due = BASE + timedelta(days=15)   # T+30 ufku içinde
    d = PersonalDebt(user_id=1, counterparty="Kirveci", direction=DebtDirection.payable,
                     amount=3000.0, is_paid=False, due_date=due)
    db.add(d); db.commit(); db.refresh(d)

    # T+0'da nakdi sabitle (aksiyon etkisi izole), sonra T+30'a projekte et.
    res = simulate_action(db, 1, "update_account_balance",
                          {"account_id": cash.id, "new_balance": 10000.0},
                          horizons_days=(0, 30), base_date=BASE)
    assert res["ok"] is True
    t0, t30 = res["snapshots"][0], res["snapshots"][1]
    assert t0["nakit_kasa"] == 10000.0
    assert t30["nakit_kasa"] == 7000.0    # borç vadesinde düştü
