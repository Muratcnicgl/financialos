"""
FEAT-013 — faiz sızıntısı sayacı (calculate_interest_leak).
Kredi + kart borçlarının aylık faiz maliyeti = borç × (aylık_oran/100). Deterministik.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType
from app.rules_engine import calculate_interest_leak, generate_cockpit
from datetime import date


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


def test_aylik_faiz_hesap(db):
    # kart 10.000 @ %4/ay = 400; kredi 30.000 @ %2/ay = 600 → toplam 1000/ay
    db.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card,
                   balance=10000.0, credit_limit=12000.0, interest_rate=4.0))
    db.add(Account(user_id=1, name="Kredi", account_type=AccountType.loan,
                   balance=30000.0, interest_rate=2.0))
    db.commit()
    r = calculate_interest_leak(1, db)
    assert r["aylik_toplam"] == 1000.0
    assert r["yillik_toplam"] == 12000.0
    assert r["kalemler"][0]["ad"] == "Kredi"       # en çok sızdıran (600) önce
    assert r["kalemler"][0]["aylik_faiz"] == 600.0


def test_oransiz_veya_borsuz_atlanir(db):
    db.add(Account(user_id=1, name="OranYok", account_type=AccountType.loan,
                   balance=5000.0, interest_rate=None))
    db.add(Account(user_id=1, name="Kapali", account_type=AccountType.loan,
                   balance=0.0, interest_rate=3.0))
    db.commit()
    r = calculate_interest_leak(1, db)
    assert r["kalemler"] == [] and r["aylik_toplam"] == 0.0


def test_nakit_yatirim_sayilmaz(db):
    db.add(Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=5000.0))
    db.add(Account(user_id=1, name="TLY", account_type=AccountType.investment,
                   balance=8000.0, interest_rate=5.0))  # yatırım faiz sızıntısı değil
    db.commit()
    assert calculate_interest_leak(1, db)["aylik_toplam"] == 0.0


def test_cockpit_faiz_sizintisi_alani(db):
    db.add(Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=1000.0))
    db.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card,
                   balance=10000.0, credit_limit=12000.0, interest_rate=4.0))
    db.commit()
    c = generate_cockpit(1, date(2026, 5, 15), db)
    assert c["faiz_sizintisi"]["aylik_toplam"] == 400.0
