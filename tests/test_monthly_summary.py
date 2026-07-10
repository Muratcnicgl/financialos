"""
A3 — Aylık özet rapor (/api/reports/monthly-summary) testi.
Gelir/gider/net + gider kategori dağılımı + önceki aya trend. Deterministik: explicit year/month.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Transaction, TransactionType


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
def client(db_session, user):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _tx(db, user_id, ttype, amount, category, d):
    db.add(Transaction(user_id=user_id, transaction_type=ttype, amount=amount,
                       category=category, transaction_date=d))


@pytest.fixture
def seed(db_session, user):
    # Mayıs 2026: gelir 50000, gider 10000 yemek + 5000 kira = 15000
    _tx(db_session, user.id, TransactionType.income, 50000, "maas", date(2026, 5, 8))
    _tx(db_session, user.id, TransactionType.expense, 10000, "yemek", date(2026, 5, 3))
    _tx(db_session, user.id, TransactionType.expense, 5000, "kira", date(2026, 5, 1))
    # Nisan 2026: gelir 50000, gider 8000
    _tx(db_session, user.id, TransactionType.income, 50000, "maas", date(2026, 4, 8))
    _tx(db_session, user.id, TransactionType.expense, 8000, "yemek", date(2026, 4, 3))
    db_session.commit()


def test_monthly_summary_aggregates(client, seed):
    r = client.get("/api/reports/monthly-summary?year=2026&month=5")
    assert r.status_code == 200
    b = r.json()
    cur = b["current"]
    assert cur["total_income"] == 50000.0
    assert cur["total_expense"] == 15000.0
    assert cur["net_change"] == 35000.0
    assert cur["savings_rate"] == 70.0
    assert cur["transaction_count"] == 3


def test_monthly_summary_category_dagilimi(client, seed):
    b = client.get("/api/reports/monthly-summary?year=2026&month=5").json()
    cats = b["current"]["expense_categories"]
    assert cats[0]["category"] == "yemek" and cats[0]["total"] == 10000.0
    assert cats[0]["percentage"] == pytest.approx(66.7, abs=0.1)
    assert cats[1]["category"] == "kira" and cats[1]["percentage"] == pytest.approx(33.3, abs=0.1)


def test_monthly_summary_onceki_ay_trend(client, seed):
    b = client.get("/api/reports/monthly-summary?year=2026&month=5").json()
    t = b["trend"]
    # gider 8000 -> 15000 = +87.5%
    assert t["expense_delta_pct"] == pytest.approx(87.5, abs=0.1)
    assert t["prev_net_change"] == 42000.0     # 50000 - 8000
    assert t["net_change_delta"] == -7000.0    # 35000 - 42000
    assert b["previous_period"]["label"] == "Nisan 2026"


def test_monthly_summary_bos_ay(client, seed):
    """İşlem olmayan ay: sıfırlar, savings_rate None, trend prev>0 ise delta None değil."""
    b = client.get("/api/reports/monthly-summary?year=2026&month=1").json()
    assert b["current"]["total_income"] == 0.0
    assert b["current"]["total_expense"] == 0.0
    assert b["current"]["savings_rate"] is None
    assert b["current"]["expense_categories"] == []


def test_monthly_summary_gecersiz_ay_422(client, seed):
    assert client.get("/api/reports/monthly-summary?year=2026&month=13").status_code == 422


def test_monthly_summary_label_turkce(client, seed):
    b = client.get("/api/reports/monthly-summary?year=2026&month=5").json()
    assert b["period"]["label"] == "Mayıs 2026"
