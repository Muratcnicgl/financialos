"""
FEAT-041 — deterministik "İLK ADIM" (recommend_next_action). Tüm sinyaller tek en-yüksek-etkili
hamleye iner: temerrüt > kriz > tahsilat > fırsat > stabil. Kurucu ilke "Rules Engine karar
verir, LLM açıklar" — öncelik koda bağlı, sağlayıcı-bağımsız.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Account, AccountType, PersonalDebt, DebtDirection,
    RecurringIncome, Transaction, TransactionType,
)
from app.rules_engine import generate_cockpit, recommend_next_action

TODAY = date(2026, 7, 12)


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


def _cash(db, bal):
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=bal))


def _card(db, bal, limit=12000):
    db.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                   balance=bal, credit_limit=limit, interest_rate=4.25))


def _rec(db, kim, amt, off):
    db.add(PersonalDebt(user_id=1, counterparty=kim, direction=DebtDirection.receivable,
                        amount=amt, due_date=TODAY + timedelta(days=off), is_paid=False))


def _act(db):
    db.commit()
    return generate_cockpit(1, TODAY, db)["sonraki_eylem"]


# ---- öncelik cascade --------------------------------------------------------

def test_temerrut_en_yuksek_oncelik(db):
    """Gecikmiş BORÇ (temerrüt) diğer her şeyin önünde."""
    _cash(db, 3000); _card(db, 11976)
    db.add(PersonalDebt(user_id=1, counterparty="Kirveci", direction=DebtDirection.payable,
                        amount=1500, due_date=TODAY - timedelta(days=5), is_paid=False))
    _rec(db, "Efe", 9000, -95)   # gecikmiş alacak da var ama temerrüt önce gelir
    a = _act(db)
    assert a["tip"] == "temerrut"
    assert "Kirveci" in a["eylem"]


def test_kriz_tahsilata_yonlendirir(db):
    """Nakit krizi öngörülürse en riskli alacağı tahsil = krizi önle."""
    _cash(db, 6000)
    db.add(Account(user_id=1, name="K1", account_type=AccountType.loan, balance=30000,
                   monthly_payment=5000, remaining_installments=6, next_payment_date=TODAY + timedelta(days=8)))
    db.add(Account(user_id=1, name="K2", account_type=AccountType.loan, balance=20000,
                   monthly_payment=4000, remaining_installments=5, next_payment_date=TODAY + timedelta(days=13)))
    db.add(RecurringIncome(user_id=1, name="KYK", amount=4000, day_of_month=8, is_active=True))
    _rec(db, "Efe", 9000, -95)
    for i in range(6):
        db.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=100.0,
                           category="market", transaction_date=TODAY - timedelta(days=i * 2)))
    a = _act(db)
    assert a["tip"] == "kriz"
    assert "Efe" in a["eylem"] and "tahsil" in a["eylem"]


def test_gecikmis_tahsilat_kriz_yokken(db):
    """Kriz yoksa da gecikmiş alacak → tahsil (nakit girişi)."""
    _cash(db, 5000); _card(db, 5000)
    _rec(db, "Efe", 9000, -95)
    a = _act(db)
    assert a["tip"] == "tahsilat"
    assert "Efe" in a["eylem"]


def test_firsat_bosta_nakit_karta(db):
    """Boşta nakit + kart borcu + acil yok → karta öde (min(boşta, kart))."""
    _cash(db, 8000); _card(db, 5000)
    a = _act(db)
    assert a["tip"] == "firsat"
    assert a["tutar"] == 5000.0          # min(8000 boşta, 5000 kart borcu)


def test_stabil_borc_var_acil_yok(db):
    """Boşta nakit eşik altı + kart borcu var + acil yok → stabil (limite sadık kal)."""
    _cash(db, 300); _card(db, 5000)      # 300 boşta < 500 eşik
    a = _act(db)
    assert a["tip"] == "stabil"


def test_borc_yoksa_none(db):
    _cash(db, 8000)
    a = _act(db)
    assert a is None


def test_pure_bos_cockpit_none():
    assert recommend_next_action({}) is None
    assert recommend_next_action({"alerts": [], "kart_borcu": 0, "kredi_borcu": 0}) is None


# ---- koç context ------------------------------------------------------------

def test_ilk_adim_koc_contextine_duser(db):
    from app.coach import _build_context_message
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=3000))
    db.add(PersonalDebt(user_id=1, counterparty="Kirveci", direction=DebtDirection.payable,
                        amount=1500, due_date=date.today() - timedelta(days=5), is_paid=False))
    db.commit()
    context, _ = _build_context_message(db, 1)
    assert "ÖNERİLEN İLK ADIM" in context
    assert "Kirveci" in context
