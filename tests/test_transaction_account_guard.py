"""
DATA-018 — işlem oluşturma bir hesabı ETKİLEMELİ (bakiyesiz "yetim" işlem yok).
account_id yoksa VE uygun varsayılan hesap bulunamıyorsa 400; hesap varsa otomatik atanır.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Account, AccountType, Transaction


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


def test_hesapsiz_ve_varsayilan_yoksa_400(client, db):
    """Hiç hesap yok + account_id verilmedi → 400 (yetim işlem oluşmaz)."""
    r = client.post("/api/transactions", json={"transaction_type": "expense", "amount": 250, "category": "market"})
    assert r.status_code == 400
    # DB'ye yetim işlem yazılmadı
    assert db.query(Transaction).count() == 0


def test_nakit_hesap_varsa_otomatik_atanir(client, db):
    """Nakit hesap var + account_id verilmedi → varsayılana atanır, bakiye düşer."""
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db.commit()
    r = client.post("/api/transactions", json={"transaction_type": "expense", "amount": 250, "category": "market"})
    assert r.status_code == 201
    assert r.json()["account_id"] is not None
    acc = db.query(Account).filter_by(user_id=1).first()
    assert acc.balance == 4750.0        # bakiye ETKİLENDİ (yetim değil)


def test_gecersiz_account_id_404(client, db):
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db.commit()
    r = client.post("/api/transactions", json={"transaction_type": "expense", "amount": 250,
                                               "category": "market", "account_id": 9999})
    assert r.status_code == 404
