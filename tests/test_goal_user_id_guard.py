"""
M75 (Wave-5) — Goal.user_id nullable=True TUTARSIZLIĞI için uygulama-katmanı kilit.

Goal, workspace-scoped 17 modelin TEK'i user_id nullable=True olan (diğerleri nullable=False).
Schema sıkılaştırması (NOT NULL) `goals` batch-recreate gerektirir; goal_allocations + goal_rules
INBOUND FK'leri var → SQLite'da riskli (M11 dersi) → Blok D (PostgreSQL) geçişine ertelendi.

Bu test schema laxity'sinin API üzerinden İSTİSMAR EDİLEMEDİĞİNİ kilitler: create_goal her zaman
user_id set eder → NULL-user goal API'den yaratılamaz. Böylece KVKK export (user_id filtresi) +
workspace scope + ownership hiçbir zaman NULL-user goal ile delinmez.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Goal


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


def _client(db_session, uid=1):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, uid)
    return TestClient(app)


def test_create_goal_user_id_daima_set_eder(db_session):
    """Her iki tip goal API'den yaratıldığında user_id NULL OLAMAZ (uygulama garantisi)."""
    try:
        c = _client(db_session, 1)
        for gtype, payload in [
            ("cash_target", {"goal_type": "cash_target", "title": "Tatil", "target_amount": 30000}),
            ("debt_freedom", {"goal_type": "debt_freedom", "title": "Borçsuz", "target_amount": 1}),
        ]:
            r = c.post("/api/goals", json=payload)
            assert r.status_code == 201, r.text
            gid = r.json()["id"]
            goal = db_session.get(Goal, gid)
            assert goal.user_id == 1, f"{gtype}: user_id NULL bırakıldı (schema laxity istismarı)"
    finally:
        app.dependency_overrides.clear()


def test_api_uzerinden_null_user_goal_yaratilamaz(db_session):
    """DB'de API akışından sonra NULL-user goal KALMAMALI (KVKK export + scope güvenliği)."""
    try:
        c = _client(db_session, 1)
        c.post("/api/goals", json={"goal_type": "cash_target", "title": "X", "target_amount": 100})
    finally:
        app.dependency_overrides.clear()
    null_user_goals = db_session.query(Goal).filter(Goal.user_id.is_(None)).count()
    assert null_user_goals == 0
