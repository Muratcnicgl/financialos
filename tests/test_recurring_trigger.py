"""
A2 — düzenli gelir/gider trigger-due (otomatik propose_action) + DEDUP.
Vadesi gelen recurring item propose olarak üretilir; aynı ay TEKRAR tetiklenmez (#047/#070/#071).
day_of_month=1 → her zaman vadesi geçmiş (deterministik).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, RecurringIncome, PendingAction, ActionStatus,
)


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=1000.0))
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


def _income(db, day=1):
    inc = RecurringIncome(user_id=1, name="KYK", amount=4000.0, day_of_month=day, is_active=True)
    db.add(inc); db.commit(); db.refresh(inc)
    return inc


def test_vadesi_gelen_gelir_propose_uretir(client, db_session):
    _income(db_session, day=1)
    r = client.post("/api/incomes/trigger-due")
    assert r.status_code == 200
    triggered = r.json()["triggered"]
    assert len(triggered) == 1
    assert triggered[0]["action_type"] == "add_transaction"
    # DB'de pending oluştu
    assert db_session.query(PendingAction).filter_by(status=ActionStatus.pending).count() == 1


def test_ayni_ay_ikinci_trigger_duplicate_uretmez(client, db_session):
    _income(db_session, day=1)
    client.post("/api/incomes/trigger-due")
    r2 = client.post("/api/incomes/trigger-due")           # ikinci kez
    assert r2.json()["triggered"] == []                    # dedup: pending zaten var
    assert db_session.query(PendingAction).count() == 1    # tek pending


def test_pasif_gelir_tetiklenmez(client, db_session):
    inc = _income(db_session, day=1)
    inc.is_active = False
    db_session.commit()
    r = client.post("/api/incomes/trigger-due")
    assert r.json()["triggered"] == []
