"""
goals router — kapsam testleri (M79). Allocation + Rule + refresh endpoint'lerinin
hata/branch yolları (404 / 403 / 409 / 422 / başarılı). İki kullanıcı (id=1, id=2)
ile ownership branch'leri kapsanır. Pattern: test_goals_ownership.py + test_goal_allocations.py.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Transaction, TransactionType, Goal, GoalAllocation, GoalRule


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


def _client(db_session, uid):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, uid)
    return TestClient(app)


def _goal(db, uid=1, title="Tatil"):
    g = Goal(user_id=uid, goal_type="cash_target", title=title,
             target_amount=Decimal("30000"), status="active")
    db.add(g); db.commit(); db.refresh(g)
    return g


def _tx(db, uid=1, amount=1000.0):
    t = Transaction(user_id=uid, transaction_type=TransactionType.income, amount=amount,
                    category="tasarruf")
    db.add(t); db.commit(); db.refresh(t)
    return t


def _rule_payload(**over):
    p = {"name": "R1", "priority": 0, "criteria": {"category": "tasarruf"},
         "allocation_type": "full", "allocation_value": None, "is_active": True}
    p.update(over)
    return p


# ============================================================
# POST /allocations
# ============================================================

def test_alloc_create_goal_yok_404(db_session):
    try:
        c1 = _client(db_session, 1)
        t = _tx(db_session)
        r = c1.post("/api/goals/99999/allocations",
                    json={"transaction_id": t.id, "amount": 100.0})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_alloc_create_tx_yok_404(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session)
        r = c1.post(f"/api/goals/{g.id}/allocations",
                    json={"transaction_id": 88888, "amount": 100.0})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_alloc_create_sifir_tutar_422(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session); t = _tx(db_session, amount=1000.0)
        r = c1.post(f"/api/goals/{g.id}/allocations",
                    json={"transaction_id": t.id, "amount": 0})
        assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_alloc_create_tx_tutarini_asan_422(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session); t = _tx(db_session, amount=1000.0)
        r = c1.post(f"/api/goals/{g.id}/allocations",
                    json={"transaction_id": t.id, "amount": 1500.0})
        assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_alloc_create_duplicate_409(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session); t = _tx(db_session, amount=1000.0)
        r1 = c1.post(f"/api/goals/{g.id}/allocations",
                     json={"transaction_id": t.id, "amount": 300.0})
        assert r1.status_code == 201
        # Aynı tx+goal ikinci kez → IntegrityError → 409
        r2 = c1.post(f"/api/goals/{g.id}/allocations",
                     json={"transaction_id": t.id, "amount": 200.0})
        assert r2.status_code == 409, r2.text
    finally:
        app.dependency_overrides.clear()


def test_alloc_create_basarili_201(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session); t = _tx(db_session, amount=1000.0)
        r = c1.post(f"/api/goals/{g.id}/allocations",
                    json={"transaction_id": t.id, "amount": 400.0})
        assert r.status_code == 201, r.text
        assert r.json()["source"] == "manual"
    finally:
        app.dependency_overrides.clear()


# ============================================================
# GET /allocations
# ============================================================

def test_alloc_list_goal_yok_404(db_session):
    try:
        c1 = _client(db_session, 1)
        r = c1.get("/api/goals/99999/allocations")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_alloc_list_basarili(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session); t = _tx(db_session, amount=1000.0)
        c1.post(f"/api/goals/{g.id}/allocations",
                json={"transaction_id": t.id, "amount": 400.0})
        r = c1.get(f"/api/goals/{g.id}/allocations")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1 and body[0]["transaction_id"] == t.id
    finally:
        app.dependency_overrides.clear()


# ============================================================
# DELETE /allocations/{id}
# ============================================================

def test_alloc_delete_yok_404(db_session):
    try:
        c1 = _client(db_session, 1)
        r = c1.delete("/api/goals/allocations/77777")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_alloc_delete_baska_kullanici_403(db_session):
    # user 1'in goal + allocation'ı; user 2 silmeye çalışır → 403
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session, uid=1); t = _tx(db_session, uid=1, amount=1000.0)
        r = c1.post(f"/api/goals/{g.id}/allocations",
                    json={"transaction_id": t.id, "amount": 400.0})
        alloc_id = r.json()["id"]
    finally:
        app.dependency_overrides.clear()

    try:
        c2 = _client(db_session, 2)
        r = c2.delete(f"/api/goals/allocations/{alloc_id}")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_alloc_delete_basarili_204(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session); t = _tx(db_session, amount=1000.0)
        r = c1.post(f"/api/goals/{g.id}/allocations",
                    json={"transaction_id": t.id, "amount": 400.0})
        alloc_id = r.json()["id"]
        r2 = c1.delete(f"/api/goals/allocations/{alloc_id}")
        assert r2.status_code == 204
        assert db_session.get(GoalAllocation, alloc_id) is None
    finally:
        app.dependency_overrides.clear()


# ============================================================
# POST /rules
# ============================================================

def test_rule_create_goal_yok_404(db_session):
    try:
        c1 = _client(db_session, 1)
        r = c1.post("/api/goals/99999/rules", json=_rule_payload())
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_rule_create_basarili_201(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session)
        r = c1.post(f"/api/goals/{g.id}/rules", json=_rule_payload(name="Tasarruf kuralı"))
        assert r.status_code == 201, r.text
        assert r.json()["name"] == "Tasarruf kuralı"
    finally:
        app.dependency_overrides.clear()


# ============================================================
# GET /rules
# ============================================================

def test_rule_list_goal_yok_404(db_session):
    try:
        c1 = _client(db_session, 1)
        r = c1.get("/api/goals/99999/rules")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_rule_list_basarili(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session)
        c1.post(f"/api/goals/{g.id}/rules", json=_rule_payload(name="A", priority=1))
        c1.post(f"/api/goals/{g.id}/rules", json=_rule_payload(name="B", priority=0))
        r = c1.get(f"/api/goals/{g.id}/rules")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        # priority asc → B (0) önce
        assert body[0]["name"] == "B"
    finally:
        app.dependency_overrides.clear()


# ============================================================
# PATCH /rules/{id}
# ============================================================

def test_rule_patch_yok_404(db_session):
    try:
        c1 = _client(db_session, 1)
        r = c1.patch("/api/goals/rules/66666", json={"name": "yeni"})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_rule_patch_baska_kullanici_403(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session, uid=1)
        r = c1.post(f"/api/goals/{g.id}/rules", json=_rule_payload())
        rule_id = r.json()["id"]
    finally:
        app.dependency_overrides.clear()

    try:
        c2 = _client(db_session, 2)
        r = c2.patch(f"/api/goals/rules/{rule_id}", json={"name": "hack"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_rule_patch_basarili(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session)
        r = c1.post(f"/api/goals/{g.id}/rules", json=_rule_payload(name="eski"))
        rule_id = r.json()["id"]
        r2 = c1.patch(f"/api/goals/rules/{rule_id}", json={"name": "yeni", "priority": 5})
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["name"] == "yeni" and body["priority"] == 5
    finally:
        app.dependency_overrides.clear()


# ============================================================
# DELETE /rules/{id}
# ============================================================

def test_rule_delete_yok_404(db_session):
    try:
        c1 = _client(db_session, 1)
        r = c1.delete("/api/goals/rules/55555")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_rule_delete_baska_kullanici_403(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session, uid=1)
        r = c1.post(f"/api/goals/{g.id}/rules", json=_rule_payload())
        rule_id = r.json()["id"]
    finally:
        app.dependency_overrides.clear()

    try:
        c2 = _client(db_session, 2)
        r = c2.delete(f"/api/goals/rules/{rule_id}")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_rule_delete_basarili_204(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session)
        r = c1.post(f"/api/goals/{g.id}/rules", json=_rule_payload())
        rule_id = r.json()["id"]
        r2 = c1.delete(f"/api/goals/rules/{rule_id}")
        assert r2.status_code == 204
        assert db_session.get(GoalRule, rule_id) is None
    finally:
        app.dependency_overrides.clear()


# ============================================================
# POST /refresh
# ============================================================

def test_refresh_goal_yok_404(db_session):
    try:
        c1 = _client(db_session, 1)
        r = c1.post("/api/goals/99999/refresh")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_refresh_basarili(db_session):
    try:
        c1 = _client(db_session, 1)
        g = _goal(db_session)
        r = c1.post(f"/api/goals/{g.id}/refresh")
        assert r.status_code == 200, r.text
        assert r.json()["id"] == g.id
    finally:
        app.dependency_overrides.clear()
