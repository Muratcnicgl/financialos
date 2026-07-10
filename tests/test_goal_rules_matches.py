"""
goal_rules._matches — kural criteria eşleşmesi (finansal allocation çekirdeği).
Her criteria dalı + boş-criteria (catch-all) davranışı kilitlenir.
"""
from __future__ import annotations

from app.models import Transaction, TransactionType, Account, AccountType
from app.goal_rules import _matches


def _tx(amount=100.0, ttype=TransactionType.expense, account_id=None, description=""):
    return Transaction(amount=amount, transaction_type=ttype,
                       account_id=account_id, description=description, category="x")


def test_tx_type_eslesme(db_session, test_user):
    tx = _tx(ttype=TransactionType.income)
    assert _matches(tx, {"tx_type": "income"}, db_session) is True
    assert _matches(tx, {"tx_type": "expense"}, db_session) is False


def test_amount_min_max_abs(db_session, test_user):
    tx = _tx(amount=500.0)
    assert _matches(tx, {"amount_min": 100}, db_session) is True
    assert _matches(tx, {"amount_min": 600}, db_session) is False
    assert _matches(tx, {"amount_max": 600}, db_session) is True
    assert _matches(tx, {"amount_max": 400}, db_session) is False


def test_account_id_eslesme(db_session, test_user):
    tx = _tx(account_id=7)
    assert _matches(tx, {"account_id": 7}, db_session) is True
    assert _matches(tx, {"account_id": 9}, db_session) is False


def test_account_type_string_ve_liste(db_session, test_user):
    acc = Account(user_id=test_user.id, name="Enpara", account_type=AccountType.cash, balance=0.0)
    db_session.add(acc); db_session.commit(); db_session.refresh(acc)
    tx = _tx(account_id=acc.id)
    assert _matches(tx, {"account_type": "cash"}, db_session) is True          # string
    assert _matches(tx, {"account_type": ["cash", "credit_card"]}, db_session) is True  # liste
    assert _matches(tx, {"account_type": "loan"}, db_session) is False


def test_account_type_hesap_yoksa_eslesmez(db_session, test_user):
    tx = _tx(account_id=None)
    assert _matches(tx, {"account_type": "cash"}, db_session) is False


def test_description_contains_case_insensitive(db_session, test_user):
    tx = _tx(description="Market ALIŞVERİŞİ")
    assert _matches(tx, {"description_contains": "market"}, db_session) is True
    assert _matches(tx, {"description_contains": "kira"}, db_session) is False


def test_bos_criteria_catch_all(db_session, test_user):
    """Boş criteria = tüm işlemlere eşleşir (catch-all kural)."""
    assert _matches(_tx(), {}, db_session) is True


def test_coklu_criteria_AND(db_session, test_user):
    """Birden çok criteria AND mantığıyla: hepsi tutmalı."""
    tx = _tx(amount=500.0, ttype=TransactionType.expense, description="market")
    assert _matches(tx, {"tx_type": "expense", "amount_min": 100, "description_contains": "market"}, db_session) is True
    assert _matches(tx, {"tx_type": "expense", "amount_min": 600}, db_session) is False  # amount tutmaz
