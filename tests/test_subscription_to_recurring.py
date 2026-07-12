"""
FEAT-006 detect→act: tespit edilen aboneliği RecurringExpense'e çevir (POST /api/subscriptions/to-recurring).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Account, AccountType, RecurringExpense


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(id=5, user_id=1, name="Enpara", account_type=AccountType.cash, balance=1000.0))
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


def test_abonelik_recurring_e_cevrilir(client, db):
    r = client.post("/api/subscriptions/to-recurring", json={
        "isim": "Netflix", "aylik_tutar": 59.99, "account_id": 5, "day_of_month": 15,
    })
    assert r.status_code == 201
    exp = db.query(RecurringExpense).filter_by(name="Netflix").first()
    assert exp is not None and float(exp.amount) == 59.99 and exp.day_of_month == 15  # ADR-030: amount Numeric(Decimal)
    assert exp.category == "abonelik"


def test_duplicate_409(client):
    body = {"isim": "Spotify", "aylik_tutar": 49.99, "account_id": 5, "day_of_month": 10}
    assert client.post("/api/subscriptions/to-recurring", json=body).status_code == 201
    assert client.post("/api/subscriptions/to-recurring", json=body).status_code == 409


def test_gecersiz_hesap_404(client):
    r = client.post("/api/subscriptions/to-recurring", json={
        "isim": "X", "aylik_tutar": 10.0, "account_id": 999, "day_of_month": 1,
    })
    assert r.status_code == 404
