"""
Integration tests for GET /api/debt-strategy/compare.
StaticPool :memory: SQLite + dependency_overrides (test_simulation_endpoint.py taklit).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Account, AccountType, Base, User


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user_alice(db_session: Session) -> User:
    u = User(name="alice_debtstrat")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def client(db_session: Session, user_alice: User):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user_alice
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ============================================================
# YARDIMCI FACTORY
# ============================================================

def _loan(db, user_id, balance, monthly_payment, interest_rate=3.0,
          remaining=12, name="Test Kredi"):
    a = Account(
        user_id=user_id, name=name,
        account_type=AccountType.loan,
        balance=balance,
        monthly_payment=monthly_payment,
        interest_rate=interest_rate,
        remaining_installments=remaining,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _card(db, user_id, balance, credit_limit=20000, name="Test Kart"):
    a = Account(
        user_id=user_id, name=name,
        account_type=AccountType.credit_card,
        balance=balance,
        credit_limit=credit_limit,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ============================================================
# TESTLER
# ============================================================

def test_compare_no_debts_returns_empty(client):
    """Borc hesabi yoksa 200 + bos yapilar."""
    resp = client.get("/api/debt-strategy/compare")

    assert resp.status_code == 200
    body = resp.json()
    assert body['debts'] == []
    assert body['snowball'] is None
    assert body['avalanche'] is None
    assert 'Aktif borc yok' in body['comparison']['recommendation_note']


def test_compare_with_debts(client, db_session, user_alice):
    """2 borc varsa 200 + snowball/avalanche dolu."""
    _loan(db_session, user_alice.id,
          balance=5000.0, monthly_payment=300.0,
          interest_rate=4.0, name="Kredi A")
    _card(db_session, user_alice.id,
          balance=8000.0, credit_limit=10000, name="Kart B")

    resp = client.get("/api/debt-strategy/compare")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body['debts']) == 2
    assert body['snowball'] is not None
    assert body['avalanche'] is not None
    assert body['snowball']['months_to_freedom'] > 0
    assert body['avalanche']['months_to_freedom'] > 0
    assert 'recommendation_note' in body['comparison']


def test_compare_extra_monthly_query_param(client, db_session, user_alice):
    """extra_monthly=500 ile total_interest_paid, extra=0'dan az olmali."""
    _loan(db_session, user_alice.id,
          balance=5000.0, monthly_payment=200.0,
          interest_rate=3.0, remaining=24, name="Kredi Tek")

    resp0   = client.get("/api/debt-strategy/compare?extra_monthly=0")
    resp500 = client.get("/api/debt-strategy/compare?extra_monthly=500")

    assert resp0.status_code == 200
    assert resp500.status_code == 200

    interest0   = resp0.json()['avalanche']['total_interest_paid']
    interest500 = resp500.json()['avalanche']['total_interest_paid']

    # Ekstra odeme faizi azaltir (ya da esit eger cok kucukse)
    assert interest500 <= interest0
    # Daha hizli bitmeli
    assert resp500.json()['avalanche']['months_to_freedom'] <= resp0.json()['avalanche']['months_to_freedom']
