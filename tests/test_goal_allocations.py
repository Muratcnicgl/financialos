"""
goals allocation endpoint — #072 over-commit koruması (sanal zenginlik / çift-sayım önlemi).
Bir tx'e tüm hedeflerdeki allocation toplamı tx tutarını AŞAMAZ. Ownership + hata yolları.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Transaction, TransactionType, Goal


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


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _goal(db, uid=1, title="Tatil"):
    from decimal import Decimal
    g = Goal(user_id=uid, goal_type="cash_target", title=title,
             target_amount=Decimal("30000"), status="active")
    db.add(g); db.commit(); db.refresh(g)
    return g


def _tx(db, uid=1, amount=1000.0):
    t = Transaction(user_id=uid, transaction_type=TransactionType.income, amount=amount,
                    category="tasarruf")
    db.add(t); db.commit(); db.refresh(t)
    return t


def test_gecerli_allocation_201(client, db_session):
    g = _goal(db_session); t = _tx(db_session, amount=1000.0)
    r = client.post(f"/api/goals/{g.id}/allocations",
                    json={"transaction_id": t.id, "amount": 400.0})
    assert r.status_code == 201


def test_072_tx_tutarini_asan_allocation_422(client, db_session):
    g = _goal(db_session); t = _tx(db_session, amount=1000.0)
    r = client.post(f"/api/goals/{g.id}/allocations",
                    json={"transaction_id": t.id, "amount": 1500.0})   # 1500 > 1000
    assert r.status_code == 422


def test_072_coklu_hedef_toplam_asan_422(client, db_session):
    """Aynı tx iki hedefe: toplam tx tutarını aşamaz (çift-sayım önlemi)."""
    g1 = _goal(db_session, title="A"); g2 = _goal(db_session, title="B")
    t = _tx(db_session, amount=1000.0)
    assert client.post(f"/api/goals/{g1.id}/allocations",
                       json={"transaction_id": t.id, "amount": 700.0}).status_code == 201
    # ikinci hedefe 400 daha → 700+400=1100 > 1000 → 422
    r = client.post(f"/api/goals/{g2.id}/allocations",
                    json={"transaction_id": t.id, "amount": 400.0})
    assert r.status_code == 422


def test_allocation_olmayan_goal_404(client, db_session):
    t = _tx(db_session)
    r = client.post("/api/goals/99999/allocations",
                    json={"transaction_id": t.id, "amount": 100.0})
    assert r.status_code == 404


def test_allocation_baska_kullanici_tx_404(client, db_session):
    g = _goal(db_session, uid=1)
    t_other = _tx(db_session, uid=2)                       # user 2'nin tx'i
    r = client.post(f"/api/goals/{g.id}/allocations",
                    json={"transaction_id": t_other.id, "amount": 100.0})
    assert r.status_code == 404
