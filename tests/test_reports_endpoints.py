"""
Reports endpoint'leri: category-breakdown (#073 yön ayrımı), net-worth-trend, upcoming-cashflow.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Transaction, TransactionType, NetWorthSnapshot


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _tx(db, ttype, amount, cat, days_ago=1):
    db.add(Transaction(user_id=1, transaction_type=ttype, amount=amount, category=cat,
                       transaction_date=date.today() - timedelta(days=days_ago)))


def test_category_breakdown_expense(client, db_session):
    _tx(db_session, TransactionType.expense, 300, "yemek")
    _tx(db_session, TransactionType.expense, 100, "yemek")
    _tx(db_session, TransactionType.expense, 100, "ulasim")
    db_session.commit()
    body = client.get("/api/reports/category-breakdown?days=30&type=expense").json()
    assert body["grand_total"] == 500.0
    yemek = [i for i in body["items"] if i["category"] == "yemek"][0]
    assert yemek["total"] == 400.0
    assert yemek["percentage"] == pytest.approx(80.0, abs=0.1)


def test_073_both_mode_gelir_gideri_ayirir(client, db_session):
    """BUG #073: 'both' modunda aynı kategori adlı gelir+gider tek total'da toplanmaz."""
    _tx(db_session, TransactionType.income, 1000, "bonus")
    _tx(db_session, TransactionType.expense, 200, "bonus")
    db_session.commit()
    body = client.get("/api/reports/category-breakdown?days=30&type=both").json()
    labels = [i["category"] for i in body["items"]]
    # yön etiketli ayrı satırlar (aynı 'bonus' iki kez, gelir/gider)
    assert any("gelir" in l for l in labels)
    assert any("gider" in l for l in labels)


def test_net_worth_trend_bos_ve_dolu(client, db_session):
    r = client.get("/api/reports/net-worth-trend?days=30")
    assert r.status_code == 200
    assert r.json()["items"] == []                       # snapshot yok
    db_session.add(NetWorthSnapshot(user_id=1, snapshot_date=date.today(),
                                    net_worth_seen=5000, net_worth_full=6000,
                                    cash=5000, card_debt=0, loan_debt=0,
                                    investment_value=0, receivables=1000))
    db_session.commit()
    body = client.get("/api/reports/net-worth-trend?days=30").json()
    assert len(body["items"]) == 1
    assert body["items"][0]["net_worth_seen"] == 5000.0


def test_upcoming_cashflow_200(client, db_session):
    r = client.get("/api/reports/upcoming-cashflow?days=30")
    assert r.status_code == 200
    assert "items" in r.json()
