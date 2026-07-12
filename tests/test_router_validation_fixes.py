"""
Router doğrulama düzeltmeleri (per-file denetim) — BUG #087, #088, #091.
StaticPool in-memory + dependency_overrides (test_simulation_endpoint.py deseni).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, Transaction, TransactionType, RecurringExpense,
)


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine):
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def user(db_session):
    u = User(name="murat")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def cash_account(db_session, user):
    a = Account(user_id=user.id, name="Enpara", account_type=AccountType.cash, balance=5000.0)
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


@pytest.fixture
def client(db_session, user):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ============================================================
# BUG #087 — transaction update: negatif/sıfır amount + yabancı account_id reddedilir
# ============================================================

def _make_expense(db, user, account, amount=500.0):
    tx = Transaction(user_id=user.id, account_id=account.id,
                     transaction_type=TransactionType.expense, amount=amount, category="yemek")
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def test_087_update_negatif_amount_422(client, db_session, user, cash_account):
    tx = _make_expense(db_session, user, cash_account)
    resp = client.put(f"/api/transactions/{tx.id}", json={"amount": -200})
    assert resp.status_code == 422
    assert "pozitif" in resp.json()["detail"].lower()


def test_087_update_sifir_amount_422(client, db_session, user, cash_account):
    tx = _make_expense(db_session, user, cash_account)
    resp = client.put(f"/api/transactions/{tx.id}", json={"amount": 0})
    assert resp.status_code == 422


def test_087_update_yabanci_account_id_404(client, db_session, user, cash_account):
    tx = _make_expense(db_session, user, cash_account)
    resp = client.put(f"/api/transactions/{tx.id}", json={"account_id": 99999})
    assert resp.status_code == 404


def test_087_gecerli_update_calisir(client, db_session, user, cash_account):
    """Kontrol: geçerli pozitif amount güncellemesi hâlâ çalışır."""
    tx = _make_expense(db_session, user, cash_account)
    resp = client.put(f"/api/transactions/{tx.id}", json={"amount": 300})
    assert resp.status_code == 200
    assert resp.json()["amount"] == 300


# ============================================================
# BUG #091 — bağlı işlemi olan hesabı silmek 500 değil 409 döner
# ============================================================

def test_091_bagli_txn_olan_hesap_silme_409(client, db_session, user, cash_account):
    _make_expense(db_session, user, cash_account)
    resp = client.delete(f"/api/accounts/{cash_account.id}")
    assert resp.status_code == 409
    assert "silinemez" in resp.json()["detail"].lower()


def test_091_bos_hesap_silinebilir(client, db_session, user):
    empty = Account(user_id=user.id, name="Bos", account_type=AccountType.cash, balance=0.0)
    db_session.add(empty)
    db_session.commit()
    db_session.refresh(empty)
    resp = client.delete(f"/api/accounts/{empty.id}")
    assert resp.status_code in (200, 204)


# ============================================================
# BUG #088 — recurring expense update: yabancı account_id reddedilir
# ============================================================

def test_088_expense_update_yabanci_account_404(client, db_session, user, cash_account):
    exp = RecurringExpense(user_id=user.id, account_id=cash_account.id, name="Netflix",
                           amount=200.0, day_of_month=5, category="abonelik")
    db_session.add(exp)
    db_session.commit()
    db_session.refresh(exp)
    resp = client.put(f"/api/expenses/recurring/{exp.id}", json={"account_id": 99999})
    assert resp.status_code == 404
