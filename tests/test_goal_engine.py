"""
H2G5 Goal Engine — birim testleri (test_01 … test_08)

Fixture'lar: conftest.py'deki db_session + test_user kullanılır.
Account, Transaction, Goal nesneleri test içinde flush ile yaratılır.
db.commit() yok — test sonunda conftest rollback ile temizlenir.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Account, AccountType,
    Goal, GoalAllocation,
    Transaction, TransactionType,
)
from app.goal_engine import (
    calculate_baseline_for_debt_freedom,
    link_transaction,
    refresh_goal,
    unlink_transaction,
)


# ──────────────────────────────────────────────
# Modül-düzeyinde autouse fixture
# ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_goal_tables(db_session):
    """Her testten ÖNCE goal tablolarını temizle.

    test_user fixture teardown'ı db.commit() çağırır ve flushed nesneleri
    DB'ye yazar. Bu commit sonraki test koşularına da taşınır. Temizleme
    her testin başında yapılır böylece izolasyon sağlanır.
    """
    from sqlalchemy import text
    db_session.execute(text("DELETE FROM goal_allocations"))
    db_session.execute(text("DELETE FROM goal_rules"))
    db_session.execute(text("DELETE FROM goals"))
    db_session.commit()
    yield


# ──────────────────────────────────────────────
# Yardımcı factory fonksiyonları
# ──────────────────────────────────────────────

def _account(db, user_id, atype=AccountType.cash, balance=10000.0, name="Test Nakit"):
    a = Account(user_id=user_id, name=name, account_type=atype, balance=balance)
    db.add(a)
    db.flush()
    return a


def _tx(db, user_id, account_id, amount=1000.0, tx_type=TransactionType.income):
    t = Transaction(
        user_id=user_id,
        account_id=account_id,
        transaction_type=tx_type,
        amount=amount,
        transaction_date=date.today(),
        description="test",
    )
    db.add(t)
    db.flush()
    return t


def _goal(db, goal_type="cash_target", target=Decimal("1000"), user_id=None):
    g = Goal(
        goal_type=goal_type,
        title="Test Hedef",
        target_amount=target,
        status="active",
        user_id=user_id,
    )
    db.add(g)
    db.flush()
    return g


# ──────────────────────────────────────────────
# TESTLER
# ──────────────────────────────────────────────

def test_01_yeni_goal_sifir_progress(db_session, test_user):
    """Yeni cash_target goal'in current_amount ve progress_percent sıfır olmalı."""
    goal = _goal(db_session, target=Decimal("10000"))
    refreshed = refresh_goal(goal.id, db_session)
    assert refreshed.current_amount == Decimal("0")
    assert refreshed.progress_percent == Decimal("0.00")


def test_02_manuel_allocation_progress_arttirir(db_session, test_user):
    """Manuel link_transaction sonrası %25 progress bekleniyor."""
    acc = _account(db_session, test_user.id)
    tx = _tx(db_session, test_user.id, acc.id, amount=250.0)
    goal = _goal(db_session, target=Decimal("1000"))

    link_transaction(goal.id, tx.id, Decimal("250"), db_session)
    db_session.refresh(goal)

    assert goal.current_amount == Decimal("250")
    assert goal.progress_percent == Decimal("25.00")


def test_03_unlink_progress_geri_duser(db_session, test_user):
    """unlink_transaction sonrası current_amount sıfıra dönmeli."""
    acc = _account(db_session, test_user.id)
    tx = _tx(db_session, test_user.id, acc.id, amount=500.0)
    goal = _goal(db_session, target=Decimal("1000"))

    alloc = link_transaction(goal.id, tx.id, Decimal("500"), db_session)
    unlink_transaction(alloc.id, db_session)
    db_session.refresh(goal)

    assert goal.current_amount == Decimal("0")
    assert goal.progress_percent == Decimal("0.00")


def test_04_hedef_ulasilinca_achieved(db_session, test_user):
    """Allocation hedef miktarını tamamlayınca status=achieved, achieved_at dolu."""
    acc = _account(db_session, test_user.id)
    tx = _tx(db_session, test_user.id, acc.id, amount=1000.0)
    goal = _goal(db_session, target=Decimal("1000"))

    link_transaction(goal.id, tx.id, Decimal("1000"), db_session)
    db_session.refresh(goal)

    assert goal.status == "achieved"
    assert goal.achieved_at is not None


def test_05_debt_freedom_baseline_ve_progress(db_session, test_user):
    """debt_freedom: borç kapatılınca progress artmalı."""
    # İki kredi hesabı yarat
    loan1 = _account(db_session, test_user.id, atype=AccountType.loan,
                     balance=3000.0, name="Kredi 1")
    loan2 = _account(db_session, test_user.id, atype=AccountType.loan,
                     balance=2000.0, name="Kredi 2")

    baseline = calculate_baseline_for_debt_freedom(test_user.id, db_session)
    assert baseline == Decimal("5000")

    goal = Goal(
        goal_type="debt_freedom",
        title="Borç Bitir",
        target_amount=Decimal("5000"),
        baseline_amount=baseline,
        status="active",
        user_id=test_user.id,
    )
    db_session.add(goal)
    db_session.flush()

    # Başlangıç: hiç ödeme yok
    refresh_goal(goal.id, db_session)
    db_session.refresh(goal)
    assert goal.progress_percent == Decimal("0.00")

    # Loan1 kapandı (bakiyesi sıfırlandı)
    loan1.balance = 0.0
    db_session.flush()
    refresh_goal(goal.id, db_session)
    db_session.refresh(goal)

    assert goal.progress_percent == Decimal("60.00")  # 3000/5000


def test_06_negatif_allocation_cekim_gibi_davranir(db_session, test_user):
    """Negatif amount = withdrawal; current ve progress buna göre düşmeli."""
    acc = _account(db_session, test_user.id)
    tx1 = _tx(db_session, test_user.id, acc.id, amount=500.0)
    tx2 = _tx(db_session, test_user.id, acc.id, amount=200.0,
              tx_type=TransactionType.expense)
    goal = _goal(db_session, target=Decimal("1000"))

    link_transaction(goal.id, tx1.id, Decimal("500"), db_session)
    link_transaction(goal.id, tx2.id, Decimal("-200"), db_session)
    db_session.refresh(goal)

    assert goal.current_amount == Decimal("300")
    assert goal.progress_percent == Decimal("30.00")


def test_07_duplikat_allocation_reddedilir(db_session, test_user):
    """Aynı (goal_id, transaction_id) çifti ikinci kez eklenirse IntegrityError."""
    acc = _account(db_session, test_user.id)
    tx = _tx(db_session, test_user.id, acc.id, amount=100.0)
    goal = _goal(db_session, target=Decimal("1000"))

    link_transaction(goal.id, tx.id, Decimal("100"), db_session)

    with pytest.raises(IntegrityError):
        link_transaction(goal.id, tx.id, Decimal("100"), db_session)

    # IntegrityError sonrası session deactive — teardown için rollback
    db_session.rollback()


def test_08_goal_silinince_allocations_cascade(db_session, test_user):
    """Goal silindiğinde GoalAllocation kayıtları cascade ile silinmeli."""
    acc = _account(db_session, test_user.id)
    tx = _tx(db_session, test_user.id, acc.id, amount=100.0)
    goal = _goal(db_session, target=Decimal("1000"))

    alloc = link_transaction(goal.id, tx.id, Decimal("100"), db_session)
    alloc_id = alloc.id

    db_session.delete(goal)
    db_session.flush()

    remaining = db_session.query(GoalAllocation) \
                          .filter(GoalAllocation.id == alloc_id).first()
    assert remaining is None
