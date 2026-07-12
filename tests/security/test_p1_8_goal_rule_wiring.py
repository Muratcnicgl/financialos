"""
P1-8 (BUG #141): GoalRule otomatik-tahsis motoru transaction create'e BAĞLANDI.
Eskiden evaluate_rules_for_transaction hiç çağrılmıyordu → kural yaratılsa da allocation yoktu.
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Account, AccountType, Goal, GoalRule, GoalAllocation


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
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


def test_p1_8_income_transaction_triggers_goal_rule_allocation(client, db):
    """Aktif GoalRule + eşleşen gelir işlemi → OTOMATİK GoalAllocation oluşur."""
    goal = Goal(goal_type="cash", user_id=1, title="Acil fon", target_amount=Decimal("10000.00"))
    db.add(goal)
    db.commit()
    db.add(GoalRule(name="Gelirin %10'u acil fona", goal_id=goal.id,
                    criteria={"tx_type": "income"}, allocation_type="percent",
                    allocation_value=Decimal("10"), priority=1, is_active=True))
    db.commit()

    # gelir işlemi POST → kural tetiklenmeli
    r = client.post("/api/transactions",
                    json={"transaction_type": "income", "amount": 2000, "category": "maas"})
    assert r.status_code == 201

    allocs = db.query(GoalAllocation).filter(GoalAllocation.goal_id == goal.id).all()
    assert len(allocs) == 1                         # otomatik tahsis oluştu
    assert allocs[0].source == "rule"
    assert allocs[0].amount == Decimal("200.00")    # 2000'in %10'u


def test_p1_8_no_rule_no_allocation(client, db):
    """Kural yoksa allocation oluşmaz (opt-in — davranış değişmez)."""
    r = client.post("/api/transactions",
                    json={"transaction_type": "income", "amount": 2000, "category": "maas"})
    assert r.status_code == 201
    assert db.query(GoalAllocation).count() == 0


def test_p2_5_transaction_limit_bounds(client, db):
    """P2-5 (BUG #154): ?limit üst/alt sınırlı — negatif/aşırı reddedilir (422)."""
    assert client.get("/api/transactions?limit=-1").status_code == 422    # alt sınır
    assert client.get("/api/transactions?limit=999999").status_code == 422  # üst sınır
    assert client.get("/api/transactions?limit=50").status_code == 200      # geçerli
