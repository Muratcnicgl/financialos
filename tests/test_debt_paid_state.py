"""
BUG #106 — borç/alacak paid-state tutarlılığı. is_paid ve paid_date her zaman uyumlu
kalmalı; çelişkili PUT'ta explicit is_paid kazanır.
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
from app.models import Base, User, PersonalDebt, DebtDirection


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


def _debt(db, **kw):
    kw.setdefault("is_paid", False)
    d = PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.payable,
                     amount=1000.0, **kw)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def test_106_celiskili_is_paid_false_paid_date_kazanan_is_paid(client, db_session):
    d = _debt(db_session)
    r = client.put(f"/api/debts/{d.id}", json={"is_paid": False, "paid_date": "2026-05-10"})
    assert r.status_code == 200
    b = r.json()
    assert b["is_paid"] is False
    assert b["paid_date"] is None  # tutarlı: ödenmedi → tarih yok


def test_106_sadece_paid_date_is_paid_turetilir(client, db_session):
    d = _debt(db_session)
    r = client.put(f"/api/debts/{d.id}", json={"paid_date": "2026-05-10"})
    b = r.json()
    assert b["is_paid"] is True
    assert b["paid_date"] == "2026-05-10"


def test_106_is_paid_true_tarih_yoksa_bugun(client, db_session):
    d = _debt(db_session)
    r = client.put(f"/api/debts/{d.id}", json={"is_paid": True})
    b = r.json()
    assert b["is_paid"] is True
    assert b["paid_date"] == date.today().isoformat()  # tutarlı: ödendi → tarih var


def test_106_is_paid_false_tarihi_temizler(client, db_session):
    d = _debt(db_session, is_paid=True, paid_date=date(2026, 5, 1))
    r = client.put(f"/api/debts/{d.id}", json={"is_paid": False})
    b = r.json()
    assert b["is_paid"] is False
    assert b["paid_date"] is None
