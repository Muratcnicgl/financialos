"""
Aksiyon yaşam döngüsü (propose→onay→execute mimarisi) router seviyesi.
approve → uygular + ActionHistory; reject → status=rejected, değişiklik yok. Ownership + hata yolları.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, PendingAction, ActionStatus, ActionHistory,
)


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add_all([User(id=1, name="murat"), User(id=2, name="baskasi")])
    s.commit()
    yield s
    s.close()


def _client(db_session, uid=1):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, uid)
    return TestClient(app)


def _cash(db, uid=1, balance=5000.0):
    a = Account(user_id=uid, name="Enpara", account_type=AccountType.cash, balance=balance)
    db.add(a); db.commit(); db.refresh(a)
    return a


def _pending(db, uid, payload, action_type="add_transaction"):
    p = PendingAction(user_id=uid, action_type=action_type, payload=json.dumps(payload),
                      summary="t", status=ActionStatus.pending)
    db.add(p); db.commit(); db.refresh(p)
    return p


def test_approve_uygular_ve_history_yazar(db_session):
    try:
        acc = _cash(db_session)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 300.0,
                                     "account_id": acc.id, "auto_update_balance": True,
                                     "category": "market"})
        r = _client(db_session).post(f"/api/actions/{p.id}/approve")
        assert r.status_code == 200
        db_session.refresh(acc); db_session.refresh(p)
        assert acc.balance == 4700.0
        assert p.status == ActionStatus.executed
        assert db_session.query(ActionHistory).count() == 1
    finally:
        app.dependency_overrides.clear()


def test_reject_degisiklik_uygulamaz(db_session):
    try:
        acc = _cash(db_session)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 300.0,
                                     "account_id": acc.id, "auto_update_balance": True})
        r = _client(db_session).post(f"/api/actions/{p.id}/reject", json={"reason": "gerek yok"})
        assert r.status_code == 200
        db_session.refresh(acc); db_session.refresh(p)
        assert acc.balance == 5000.0                      # değişmedi
        assert p.status == ActionStatus.rejected
    finally:
        app.dependency_overrides.clear()


def test_approve_olmayan_404(db_session):
    try:
        assert _client(db_session).post("/api/actions/99999/approve").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_approve_zaten_executed_422(db_session):
    try:
        acc = _cash(db_session)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 100.0,
                                     "account_id": acc.id, "auto_update_balance": True})
        p.status = ActionStatus.executed
        db_session.commit()
        r = _client(db_session).post(f"/api/actions/{p.id}/approve")
        assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_baska_kullanici_approve_edemez(db_session):
    try:
        acc = _cash(db_session, uid=1)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 100.0,
                                     "account_id": acc.id, "auto_update_balance": True})
    finally:
        app.dependency_overrides.clear()
    try:
        r = _client(db_session, uid=2).post(f"/api/actions/{p.id}/approve")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
