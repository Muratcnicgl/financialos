"""
NET DEĞER KORUNUMU — executor aksiyonlarının net-değere etkisi DOĞRU olmalı.
BUG #113 tam bir net-değer bug'ıydı (alacak tahsili net değeri yanlış düşürüyordu); bu testler
o SINIFI net-değer seviyesinde kilitler. Kaynak: generate_cockpit net_deger_tam (alacak dahil).
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Account, AccountType, PersonalDebt, DebtDirection,
    PendingAction, ActionStatus,
)
from app.action_executor import execute_pending_action
from app.rules_engine import generate_cockpit

TODAY = date(2026, 5, 10)


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


def _pending(db, action_type, payload):
    p = PendingAction(user_id=1, action_type=action_type, payload=json.dumps(payload),
                      summary="t", status=ActionStatus.pending)
    db.add(p); db.commit(); db.refresh(p)
    return p


def _net_tam(db):
    return generate_cockpit(1, TODAY, db)["net_deger_tam"]


def test_113_alacak_tahsili_net_deger_korunur(db):
    """Alacak tahsili net-NÖTR olmalı (alacak → nakit). #113 öncesi net değer DÜŞÜYORDU."""
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                        amount=1000.0, is_paid=False, due_date=date(2026, 5, 15)))
    db.commit()

    before = _net_tam(db)
    p = _pending(db, "mark_debt_paid", {"debt_id": db.query(PersonalDebt).first().id})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True
    after = _net_tam(db)
    assert abs(after - before) < 0.01, f"tahsilat net-değeri değiştirdi: {before} -> {after}"


def test_116_borc_odemesi_net_deger_korunur(db):
    """
    BUG #116 fix: net_deger_tam artık kişisel payable'ı yükümlülük sayıyor (simetri). Bu yüzden
    borç ödemesi net-NÖTR: önceden payable net değeri düşürüyordu (−1000), ödeme nakdi düşürür
    (−1000) ama payable yükümlülüğü kalkar (+1000) → net değişim SIFIR.
    """
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.payable,
                        amount=1000.0, is_paid=False, due_date=date(2026, 5, 15)))
    db.commit()

    before = _net_tam(db)
    p = _pending(db, "mark_debt_paid", {"debt_id": db.query(PersonalDebt).first().id})
    execute_pending_action(db, p.id, 1)
    after = _net_tam(db)
    assert abs(after - before) < 0.01, f"borç ödemesi net-nötr olmalı: {before} -> {after}"


def test_116_odenmemis_payable_net_degeri_dusor(db):
    """Ödenmemiş kişisel borç net_deger_tam'ı azaltır (yükümlülük) — realist, şişkin değil."""
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db.commit()
    net_borcsuz = _net_tam(db)
    db.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.payable,
                        amount=1000.0, is_paid=False, due_date=date(2026, 5, 15)))
    db.commit()
    net_borclu = _net_tam(db)
    assert abs((net_borcsuz - net_borclu) - 1000.0) < 0.01


def test_add_transaction_expense_net_deger_dusor(db):
    """Nakit gider net değeri tam tutar kadar DÜŞÜRÜR."""
    acc = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0)
    db.add(acc); db.commit(); db.refresh(acc)
    before = _net_tam(db)
    p = _pending(db, "add_transaction", {
        "transaction_type": "expense", "amount": 300.0, "account_id": acc.id,
        "auto_update_balance": True, "category": "market"})
    execute_pending_action(db, p.id, 1)
    after = _net_tam(db)
    assert abs((before - after) - 300.0) < 0.01


def test_sell_investment_net_deger_sadece_stopaj_kadar_azalir(db):
    """Piyasa fiyatından satış: net değer yalnız STOPAJ kadar azalır (gerisi nakde döner)."""
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=0.0))
    inv = Account(user_id=1, name="TLY", account_type=AccountType.investment,
                  lot_count=10.0, cost_per_lot=800.0, current_price=1000.0, balance=10000.0)
    db.add(inv); db.commit(); db.refresh(inv)
    cash_id = db.query(Account).filter_by(account_type=AccountType.cash).first().id

    before = _net_tam(db)
    # 4 lot @ 1000 (maliyet 800) → kâr 800, stopaj = 800*0.175 = 140
    p = _pending(db, "sell_investment", {
        "investment_id": inv.id, "lots_to_sell": 4.0, "actual_price": 1000.0,
        "credit_to_account_id": cash_id})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True
    after = _net_tam(db)
    assert abs((before - after) - 140.0) < 0.01, f"net değer stopaj dışında değişti: {before}->{after}"
