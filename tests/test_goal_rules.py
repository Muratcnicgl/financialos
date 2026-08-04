"""
H2G5 Goal Rules — birim testleri (test_09 … test_14)

Fixture'lar: conftest.py'deki db_session + test_user.
db.commit() yok — test sonunda conftest rollback ile temizlenir.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models import (
    Account, AccountType,
    Goal, GoalRule,
    Transaction, TransactionType,
)
from app.goal_rules import evaluate_rules_for_transaction


# ──────────────────────────────────────────────
# Modül-düzeyinde autouse fixture
# ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_goal_tables(db_session):
    """Her testten ÖNCE goal tablolarını temizle (cross-run pollution önleme)."""
    from sqlalchemy import text
    db_session.execute(text("DELETE FROM goal_allocations"))
    db_session.execute(text("DELETE FROM goal_rules"))
    db_session.execute(text("DELETE FROM goals"))
    db_session.commit()
    yield


# ──────────────────────────────────────────────
# Yardımcı factory fonksiyonları
# ──────────────────────────────────────────────

def _account(db, user_id, atype=AccountType.cash, balance=10000.0):
    a = Account(user_id=user_id, name="Test", account_type=atype, balance=balance)
    db.add(a)
    db.flush()
    return a


def _tx(db, user_id, account_id, amount=1000.0,
        tx_type=TransactionType.income, description=""):
    t = Transaction(
        user_id=user_id,
        account_id=account_id,
        transaction_type=tx_type,
        amount=amount,
        transaction_date=date.today(),
        description=description,
    )
    db.add(t)
    db.flush()
    return t


def _goal(db, user_id=None, target=Decimal("10000")):
    g = Goal(
        goal_type="cash_target",
        title="Test Goal",
        target_amount=target,
        status="active",
        user_id=user_id,
    )
    db.add(g)
    db.flush()
    return g


def _rule(db, goal_id, criteria, alloc_type="full", alloc_value=None,
          priority=0, is_active=True, name="Test Kural"):
    r = GoalRule(
        goal_id=goal_id,
        name=name,
        criteria=criteria,
        allocation_type=alloc_type,
        allocation_value=alloc_value,
        is_active=is_active,
        priority=priority,
    )
    db.add(r)
    db.flush()
    return r


# ──────────────────────────────────────────────
# TESTLER
# ──────────────────────────────────────────────

def test_09_basit_kural_tx_type_eslesmesi(db_session, test_user):
    """tx_type=transfer kuralı, transfer tipindeki tx'e eşleşmeli."""
    acc = _account(db_session, test_user.id)
    goal = _goal(db_session, user_id=test_user.id)
    _rule(db_session, goal.id, criteria={"tx_type": "transfer"}, alloc_type="full")

    tx = _tx(db_session, test_user.id, acc.id, amount=1500.0,
             tx_type=TransactionType.transfer)
    created = evaluate_rules_for_transaction(tx.id, db_session)

    assert len(created) == 1
    assert created[0].amount == Decimal("1500")
    assert created[0].source == "rule"


def test_10_percent_allocation_hesabi(db_session, test_user):
    """allocation_type=percent, %30 oranı doğru hesaplanmalı."""
    acc = _account(db_session, test_user.id)
    goal = _goal(db_session, user_id=test_user.id)
    _rule(db_session, goal.id,
          criteria={"tx_type": "income"},
          alloc_type="percent",
          alloc_value=Decimal("30"))

    tx = _tx(db_session, test_user.id, acc.id, amount=10000.0,
             tx_type=TransactionType.income)
    created = evaluate_rules_for_transaction(tx.id, db_session)

    assert len(created) == 1
    assert created[0].amount == Decimal("3000.00")


def test_11_fixed_allocation_hesabi(db_session, test_user):
    """allocation_type=fixed, sabit 500 TL allocate edilmeli."""
    acc = _account(db_session, test_user.id)
    goal = _goal(db_session, user_id=test_user.id)
    _rule(db_session, goal.id,
          criteria={"tx_type": "income"},
          alloc_type="fixed",
          alloc_value=Decimal("500"))

    tx = _tx(db_session, test_user.id, acc.id, amount=8000.0,
             tx_type=TransactionType.income)
    created = evaluate_rules_for_transaction(tx.id, db_session)

    assert len(created) == 1
    assert created[0].amount == Decimal("500")


def test_12_inactive_kural_atlanir(db_session, test_user):
    """is_active=False olan kural değerlendirilmemeli."""
    acc = _account(db_session, test_user.id)
    goal = _goal(db_session, user_id=test_user.id)
    _rule(db_session, goal.id,
          criteria={"tx_type": "transfer"},
          alloc_type="full",
          is_active=False)

    tx = _tx(db_session, test_user.id, acc.id, amount=1000.0,
             tx_type=TransactionType.transfer)
    created = evaluate_rules_for_transaction(tx.id, db_session)

    assert len(created) == 0


def test_13_birden_fazla_kural_stack_eder(db_session, test_user):
    """Aynı tx iki farklı goal'deki kurala eşleşirse ikisi de allocate edilmeli."""
    acc = _account(db_session, test_user.id)
    g1 = _goal(db_session, user_id=test_user.id, target=Decimal("5000"))
    g2 = _goal(db_session, user_id=test_user.id, target=Decimal("5000"))

    _rule(db_session, g1.id,
          criteria={"tx_type": "income"},
          alloc_type="percent", alloc_value=Decimal("20"),
          priority=1, name="R1")
    _rule(db_session, g2.id,
          criteria={"tx_type": "income"},
          alloc_type="percent", alloc_value=Decimal("30"),
          priority=2, name="R2")

    tx = _tx(db_session, test_user.id, acc.id, amount=10000.0,
             tx_type=TransactionType.income)
    created = evaluate_rules_for_transaction(tx.id, db_session)

    assert len(created) == 2
    amounts = sorted([a.amount for a in created])
    assert amounts == [Decimal("2000.00"), Decimal("3000.00")]


def test_14_paused_goal_allocation_atlanir(db_session, test_user):
    """status=paused olan goal için kural eşleşse bile allocation yaratılmamalı."""
    acc = _account(db_session, test_user.id)
    goal = _goal(db_session, user_id=test_user.id)
    goal.status = "paused"
    db_session.flush()

    _rule(db_session, goal.id,
          criteria={"tx_type": "income"},
          alloc_type="full")

    tx = _tx(db_session, test_user.id, acc.id, amount=1000.0,
             tx_type=TransactionType.income)
    created = evaluate_rules_for_transaction(tx.id, db_session)

    assert len(created) == 0


# ──────────────────────────────────────────────
# BUG #162 — Çapraz-kullanıcı / çapraz-workspace kural sızıntısı (kapalı-beta izolasyon denetimi)
# ──────────────────────────────────────────────

def _user(db, name):
    from app.models import User
    u = User(name=name)
    db.add(u)
    db.flush()
    return u


def test_15_baska_kullanicinin_kurali_benim_islemime_uygulanmaz(db_session, test_user):
    """BUG #162: B'nin aktif kuralı, A'nın işlemine allocation YARATMAMALI.

    Eskiden evaluate_rules_for_transaction TÜM kullanıcıların aktif kurallarını çekiyordu →
    A para kazandığında B'nin hedefine allocation düşüyordu (B, A'nın tutarını + transaction_id'sini
    kendi allocation listesinde görürdü). Tek-kullanıcıda görünmez, kapalı-betada gerçek sızıntı.
    """
    diger = _user(db_session, "diger_kullanici")
    acc = _account(db_session, test_user.id)

    # B'nin her gelire uyan kuralı
    b_goal = _goal(db_session, user_id=diger.id)
    _rule(db_session, b_goal.id, criteria={"tx_type": "income"}, alloc_type="full")

    tx = _tx(db_session, test_user.id, acc.id, amount=5000.0,
             tx_type=TransactionType.income)
    created = evaluate_rules_for_transaction(tx.id, db_session)

    assert created == [], "Başka kullanıcının kuralı bu işleme uygulandı — veri sızıntısı"


def test_16_baska_workspace_kurali_uygulanmaz(db_session, test_user):
    """BUG #162: farklı workspace'in kuralı bu workspace'in işlemine uygulanmamalı."""
    acc = _account(db_session, test_user.id)

    yabanci_goal = _goal(db_session, user_id=test_user.id)
    yabanci_goal.workspace_id = 999          # başka workspace
    db_session.flush()
    _rule(db_session, yabanci_goal.id, criteria={"tx_type": "income"}, alloc_type="full")

    tx = _tx(db_session, test_user.id, acc.id, amount=5000.0,
             tx_type=TransactionType.income)
    tx.workspace_id = 1
    db_session.flush()

    created = evaluate_rules_for_transaction(tx.id, db_session)

    assert created == [], "Başka workspace'in kuralı uygulandı — workspace izolasyonu kırık"


def test_17_ayni_workspace_farkli_uye_kurali_UYGULANIR(db_session, test_user):
    """ADR-036 pozitif kontrol: paylaşılan workspace'te aile üyesinin kuralı GEÇERLİ.

    Fix aşırı-daraltmamalı — workspace ortak veri alanıdır; aynı workspace içindeki
    başka üyenin hedef kuralı o workspace'in işlemine uygulanır.
    """
    aile_uyesi = _user(db_session, "aile_uyesi")
    acc = _account(db_session, test_user.id)

    ortak_goal = _goal(db_session, user_id=aile_uyesi.id)
    ortak_goal.workspace_id = 7
    db_session.flush()
    _rule(db_session, ortak_goal.id, criteria={"tx_type": "income"}, alloc_type="full")

    tx = _tx(db_session, test_user.id, acc.id, amount=5000.0,
             tx_type=TransactionType.income)
    tx.workspace_id = 7
    db_session.flush()

    created = evaluate_rules_for_transaction(tx.id, db_session)

    assert len(created) == 1, "Aynı workspace'teki üyenin kuralı uygulanmadı (fix aşırı daralttı)"
    assert created[0].amount == Decimal("5000")
