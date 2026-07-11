"""
FEAT-014 — kredi konsolidasyon simülatörü (nötr karşılaştırma aracı, tavsiye değil).
calculate_consolidation_baseline (assumption-free eşik) + simulate_consolidation (what-if)
+ endpoint + cockpit/koç entegrasyonu.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Account, AccountType
from app.debt_strategy import (
    DebtItem, calculate_consolidation_baseline, simulate_consolidation, _annuity_payment,
)


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


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _loan(aid, bal, rate):
    return DebtItem(account_id=aid, name=f"Kredi{aid}", account_type="loan",
                    balance=bal, interest_rate_monthly=rate, min_payment=bal / 12)


# ---- _annuity_payment ------------------------------------------------------

def test_annuity_faizsiz_esit_bolusum():
    assert _annuity_payment(12000, 0.0, 12) == 1000.0     # r=0 → anapara/vade


def test_annuity_faizli_taksit_makul():
    p = _annuity_payment(100000, 2.0, 24)
    assert 5000 < p < 5600                                # ~5289 TL/ay
    assert p * 24 > 100000                                # toplam > anapara (faiz var)


# ---- calculate_consolidation_baseline (assumption-free) --------------------

def test_baseline_tek_borc_none(db):
    assert calculate_consolidation_baseline([_loan(1, 10000, 3.0)]) is None


def test_baseline_agirlikli_ortalama(db):
    # 10000@%2 + 30000@%4 → ağırlıklı = (20000+120000)/40000 = %3.5
    b = calculate_consolidation_baseline([_loan(1, 10000, 2.0), _loan(2, 30000, 4.0)])
    assert b["borc_adet"] == 2
    assert b["toplam_bakiye"] == 40000.0
    assert b["agirlikli_ort_oran"] == 3.5
    assert b["en_yuksek_oran"] == 4.0
    assert b["en_dusuk_oran"] == 2.0


# ---- simulate_consolidation (what-if) --------------------------------------

def test_simulate_oran_avantaji_esigi(db):
    debts = [_loan(1, 10000, 2.0), _loan(2, 30000, 4.0)]   # ağırlıklı %3.5
    ucuz = simulate_consolidation(debts, new_rate_monthly=3.0, term_months=24)
    pahali = simulate_consolidation(debts, new_rate_monthly=4.0, term_months=24)
    assert ucuz["oran_avantajli"] is True                  # %3.0 < %3.5 eşik
    assert pahali["oran_avantajli"] is False               # %4.0 > %3.5 eşik
    assert ucuz["yeni_toplam_faiz"] < pahali["yeni_toplam_faiz"]
    assert ucuz["vade_ay"] == 24
    # toplam_odeme yuvarlanmamış taksit×vade üzerinden → yuvarlanmış taksit×vade'ye çok yakın
    assert ucuz["yeni_toplam_odeme"] == pytest.approx(ucuz["yeni_taksit"] * 24, abs=0.5)


def test_simulate_tek_borc_none(db):
    assert simulate_consolidation([_loan(1, 10000, 3.0)], 2.0, 24) is None


def test_simulate_gecersiz_vade_none(db):
    assert simulate_consolidation([_loan(1, 10000, 2.0), _loan(2, 30000, 4.0)], 3.0, 0) is None


# ---- endpoint --------------------------------------------------------------

def test_endpoint_consolidation(client, db):
    db.add(Account(user_id=1, name="K1", account_type=AccountType.loan, balance=10000, interest_rate=2.0, monthly_payment=900))
    db.add(Account(user_id=1, name="K2", account_type=AccountType.loan, balance=30000, interest_rate=4.0, monthly_payment=2700))
    db.commit()
    r = client.get("/api/debt-strategy/consolidation?rate=3.0&term=24")
    assert r.status_code == 200
    body = r.json()
    assert body["agirlikli_ort_oran"] == 3.5
    assert body["oran_avantajli"] is True
    assert body["yeni_taksit"] > 0


def test_endpoint_tek_borc_404(client, db):
    db.add(Account(user_id=1, name="K1", account_type=AccountType.loan, balance=10000, interest_rate=2.0, monthly_payment=900))
    db.commit()
    assert client.get("/api/debt-strategy/consolidation?rate=3.0&term=24").status_code == 404


def test_endpoint_gecersiz_oran_422(client, db):
    # rate > 20 → Query validation reddi
    assert client.get("/api/debt-strategy/consolidation?rate=99&term=24").status_code == 422


# ---- cockpit + koç ---------------------------------------------------------

def test_cockpit_konsolidasyon_alani(db):
    from app.rules_engine import generate_cockpit
    from datetime import date
    db.add(Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=1000))
    db.add(Account(user_id=1, name="K1", account_type=AccountType.loan, balance=10000, interest_rate=2.0, monthly_payment=900))
    db.add(Account(user_id=1, name="K2", account_type=AccountType.loan, balance=30000, interest_rate=4.0, monthly_payment=2700))
    db.commit()
    c = generate_cockpit(1, date(2026, 7, 12), db)
    assert c["konsolidasyon"]["agirlikli_ort_oran"] == 3.5


def test_koc_contextine_duser(db):
    from app.coach import _build_context_message
    db.add(Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=1000))
    db.add(Account(user_id=1, name="K1", account_type=AccountType.loan, balance=10000, interest_rate=2.0, monthly_payment=900))
    db.add(Account(user_id=1, name="K2", account_type=AccountType.loan, balance=30000, interest_rate=4.0, monthly_payment=2700))
    db.commit()
    context, _ = _build_context_message(db, 1)
    assert "KONSOLİDASYON EŞİĞİ" in context
