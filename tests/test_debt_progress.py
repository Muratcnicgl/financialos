"""
FEAT-017 — borç ödeme ilerlemesi (motivasyon). En eski NetWorthSnapshot'tan bugüne toplam
borç ne kadar azaldı. Borç-batık için davranışsal momentum (Ramsey).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, NetWorthSnapshot
from app.rules_engine import calculate_debt_progress

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


def _snap(db, when, card, loan):
    db.add(NetWorthSnapshot(user_id=1, snapshot_date=when, net_worth_seen=0, net_worth_full=0,
                            cash=0, card_debt=card, loan_debt=loan, investment_value=0, receivables=0))
    db.commit()


def test_gecmis_yoksa_none(db):
    assert calculate_debt_progress(1, TODAY, db, 10000) is None


def test_hafta_altinda_none(db):
    _snap(db, TODAY - timedelta(days=3), 12000, 50000)   # <7 gün → anlamsız
    assert calculate_debt_progress(1, TODAY, db, 60000) is None


def test_baslangic_borc_sifir_none(db):
    _snap(db, TODAY - timedelta(days=30), 0, 0)           # borçsuz başlangıç → oran anlamsız
    assert calculate_debt_progress(1, TODAY, db, 5000) is None


def test_ilerleme_hesabi(db):
    _snap(db, TODAY - timedelta(days=60), 12000, 58000)   # başlangıç 70000
    r = calculate_debt_progress(1, TODAY, db, 55000)      # şimdi 55000 → 15000 ödendi
    assert r["baslangic_borc"] == 70000.0
    assert r["guncel_borc"] == 55000.0
    assert r["odendi"] == 15000.0
    assert r["yuzde"] == round(15000 / 70000 * 100, 1)    # ~21.4
    assert r["ilerleme"] is True
    assert r["gun"] == 60


def test_borc_buyuduyse_ilerleme_false(db):
    _snap(db, TODAY - timedelta(days=30), 10000, 40000)   # başlangıç 50000
    r = calculate_debt_progress(1, TODAY, db, 56000)      # şimdi 56000 → borç büyüdü
    assert r["odendi"] == -6000.0
    assert r["ilerleme"] is False


def test_en_eski_snapshot_baz_alinir(db):
    _snap(db, TODAY - timedelta(days=90), 15000, 60000)   # EN eski (baz)
    _snap(db, TODAY - timedelta(days=10), 13000, 55000)   # ara snapshot
    r = calculate_debt_progress(1, TODAY, db, 50000)
    assert r["baslangic_borc"] == 75000.0                 # en eski baz alınır
    assert r["gun"] == 90


def test_cockpit_borc_ilerleme_alani(db):
    from app.rules_engine import generate_cockpit
    from app.models import Account, AccountType
    db.add(Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=1000))
    db.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card,
                   balance=8000, credit_limit=12000, interest_rate=4.25))
    _snap(db, TODAY - timedelta(days=30), 12000, 0)       # başlangıç kart 12000
    r = generate_cockpit(1, TODAY, db)
    assert r["borc_ilerleme"] is not None
    assert r["borc_ilerleme"]["odendi"] == 4000.0         # 12000 → 8000
