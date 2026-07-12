"""
FEAT-012 — borçsuzluk tarihi cockpit metriği (borc_ozgurluk).
Avalanche calc'tan kalan_ay + borcsuz_tarih + toplam_faiz. Deterministik izole DB.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType
from app.rules_engine import generate_cockpit

TODAY = date(2026, 5, 15)


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


def test_borcsuz_borc_ozgurluk_none(db):
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=5000.0))
    db.commit()
    assert generate_cockpit(1, TODAY, db)["borc_ozgurluk"] is None   # borç yok


def test_borclu_borc_ozgurluk_metrigi(db):
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=2000.0))
    db.add(Account(user_id=1, name="K", account_type=AccountType.loan, balance=12000.0,
                   monthly_payment=2000.0, remaining_installments=8, interest_rate=2.0))
    db.commit()
    bo = generate_cockpit(1, TODAY, db)["borc_ozgurluk"]
    assert bo is not None
    assert bo["kalan_ay"] >= 1
    assert bo["asla_bitmez"] is False
    assert bo["toplam_faiz"] >= 0
