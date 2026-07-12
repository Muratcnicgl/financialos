"""
execute_pending_action uçtan uca — mimari çekirdek (propose → onay → execute) kapsamı.
Kapsam ölçümü action_executor'ı %49'da gösterdi; kritik handler'lar (mark_debt_paid,
update_account_balance, update_fund_price, dispatch/hata yolları) + MC1 enforcement burada
uçtan uca test edilir. Founding "sıfır hata" + Master Checkpoint mandatı.
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


def _pending(db, action_type, payload, user_id=1):
    p = PendingAction(user_id=user_id, action_type=action_type,
                      payload=json.dumps(payload), summary="test", status=ActionStatus.pending)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ---- add_transaction ----
def test_execute_add_transaction_bakiye_gunceller(db):
    acc = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=1000.0)
    db.add(acc); db.commit(); db.refresh(acc)
    p = _pending(db, "add_transaction", {
        "transaction_type": "expense", "amount": 300.0, "account_id": acc.id,
        "auto_update_balance": True, "category": "market",
    })
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True
    db.refresh(acc); db.refresh(p)
    assert acc.balance == 700.0
    assert p.status == ActionStatus.executed


# ---- update_account_balance + MC1 ----
def test_execute_update_account_balance(db):
    acc = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=1000.0)
    db.add(acc); db.commit(); db.refresh(acc)
    p = _pending(db, "update_account_balance", {"account_id": acc.id, "new_balance": 2500.0})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True
    db.refresh(acc)
    assert acc.balance == 2500.0


def test_execute_update_account_balance_emanet_MC1_reddedilir(db):
    emanet = Account(user_id=1, name="Altın Emanet", account_type=AccountType.investment,
                     balance=20000.0, is_emanet=True)
    db.add(emanet); db.commit(); db.refresh(emanet)
    p = _pending(db, "update_account_balance", {"account_id": emanet.id, "new_balance": 0.0})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is False
    assert "emanet" in (res.get("error") or "").lower()
    db.refresh(emanet); db.refresh(p)
    assert emanet.balance == 20000.0            # dokunulmadı
    assert p.status == ActionStatus.failed


# ---- mark_debt_paid (BUG #113: TEK aksiyon, nakdi de hareket ettirir) ----
def test_execute_mark_debt_paid_alacak_tahsili_nakit_artar(db):
    """BUG #113: alacak tahsili nakdi ARTIRIR (tek aksiyon; executor↔sim tutarlı)."""
    cash = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0)
    debt = PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                        amount=1000.0, is_paid=False, due_date=date(2026, 5, 10))
    db.add_all([cash, debt]); db.commit(); db.refresh(cash); db.refresh(debt)
    p = _pending(db, "mark_debt_paid", {"debt_id": debt.id})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True
    db.refresh(debt); db.refresh(cash)
    assert debt.is_paid is True and debt.paid_date is not None
    assert cash.balance == 6000.0               # tahsilat → nakit +1000


def test_execute_mark_debt_paid_borc_odemesi_nakit_azalir(db):
    """BUG #113: borç ödemesi nakdi AZALTIR."""
    cash = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0)
    debt = PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.payable,
                        amount=1000.0, is_paid=False, due_date=date(2026, 5, 10))
    db.add_all([cash, debt]); db.commit(); db.refresh(cash); db.refresh(debt)
    p = _pending(db, "mark_debt_paid", {"debt_id": debt.id})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True
    db.refresh(cash)
    assert cash.balance == 4000.0               # ödeme → nakit -1000


def test_execute_mark_debt_paid_zaten_odenmis_reddedilir(db):
    debt = PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.payable,
                        amount=1000.0, is_paid=True, paid_date=date(2026, 5, 1))
    db.add(debt); db.commit(); db.refresh(debt)
    p = _pending(db, "mark_debt_paid", {"debt_id": debt.id})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is False


# ---- update_fund_price ----
def test_execute_update_fund_price(db):
    inv = Account(user_id=1, name="TLY", account_type=AccountType.investment,
                  lot_count=10.0, cost_per_lot=800.0, current_price=1000.0, balance=10000.0)
    db.add(inv); db.commit(); db.refresh(inv)
    p = _pending(db, "update_fund_price", {"account_id": inv.id, "new_price": 1200.0})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True
    db.refresh(inv)
    assert inv.current_price == 1200.0
    assert inv.balance == 10 * 1200.0           # balance = lot * yeni fiyat


# ---- dispatch / hata yolları ----
def test_execute_zaten_executed_reddedilir(db):
    p = _pending(db, "add_transaction", {"transaction_type": "income", "amount": 1.0})
    p.status = ActionStatus.executed
    db.commit()
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is False
    assert "executed" in (res.get("error") or "").lower() or "durum" in (res.get("error") or "").lower()


def test_execute_bilinmeyen_action_type_failed(db):
    p = _pending(db, "kendini_imha_et", {})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is False
    db.refresh(p)
    assert p.status == ActionStatus.failed


def test_execute_bozuk_payload_failed(db):
    p = PendingAction(user_id=1, action_type="add_transaction", payload="{bozuk json",
                      summary="x", status=ActionStatus.pending)
    db.add(p); db.commit(); db.refresh(p)
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is False


def test_execute_baska_kullanici_bulunamaz(db):
    db.add(User(id=2, name="baskasi")); db.commit()
    p = _pending(db, "add_transaction", {"transaction_type": "income", "amount": 1.0}, user_id=1)
    res = execute_pending_action(db, p.id, 2)      # user 2, user 1'in aksiyonu
    assert res["success"] is False
    assert "bulunamadi" in (res.get("error") or "").lower()


# ============================================================
# SEC-032 — para-hareketi handler'ları non-finite payload'ı reddeder (DB bozulmaz)
# ============================================================
import math  # noqa: E402


def test_update_balance_nan_reddedilir_bakiye_degismez(db):
    acc = Account(id=1, user_id=1, name="Nakit", account_type=AccountType.cash, balance=5000.0)
    db.add(acc); db.commit()
    p = _pending(db, "update_account_balance",
                 {"account_id": 1, "new_balance": float("nan")})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is False
    db.refresh(acc)
    assert acc.balance == 5000.0                    # mutasyon YOK
    assert math.isfinite(acc.balance)
    db.refresh(p)
    assert p.status == ActionStatus.failed


def test_add_transaction_inf_reddedilir(db):
    acc = Account(id=1, user_id=1, name="Nakit", account_type=AccountType.cash, balance=5000.0)
    db.add(acc); db.commit()
    p = _pending(db, "add_transaction",
                 {"transaction_type": "expense", "amount": float("inf"), "account_id": 1})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is False
    db.refresh(acc)
    assert acc.balance == 5000.0                    # bakiye dokunulmadı


def test_sell_investment_nan_lots_reddedilir_lot_degismez(db):
    """NaN lots eskiden `<=0` ve `>lot` guard'larını atlayıp DB'ye nan yazabilirdi."""
    inv = Account(id=1, user_id=1, name="TLY", account_type=AccountType.investment,
                  lot_count=10.0, cost_per_lot=100.0, current_price=120.0, balance=1200.0)
    cash = Account(id=2, user_id=1, name="Nakit", account_type=AccountType.cash, balance=0.0)
    db.add_all([inv, cash]); db.commit()
    p = _pending(db, "sell_investment",
                 {"investment_id": 1, "lots_to_sell": float("nan"), "credit_to_account_id": 2})
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is False
    db.refresh(inv); db.refresh(cash)
    assert inv.lot_count == 10.0                     # lot dokunulmadı
    assert cash.balance == 0.0                       # nakit dokunulmadı
    assert math.isfinite(inv.lot_count)
