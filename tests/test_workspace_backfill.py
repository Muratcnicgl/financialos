"""
M40 (ADR-036) — create_personal_workspaces backfill testleri (in-memory, session-injected).

run(db) her User için personal workspace yaratır + owner membership + scoped satırları
taşır; idempotent; Goal.user_id NULL global hedefi atlar.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.models import (
    User, Workspace, WorkspaceMembership, WorkspaceRole,
    Account, Transaction, Goal, MasterCheckpoint,
)
from scripts.create_personal_workspaces import run


@pytest.fixture
def seeded(db_session):
    u1 = User(name="murat")
    u2 = User(name="es")
    db_session.add_all([u1, u2])
    db_session.commit()
    # u1'in kayıtları (workspace_id NULL)
    db_session.add_all([
        Account(user_id=u1.id, name="Nakit", account_type="cash"),
        Transaction(user_id=u1.id, transaction_type="expense", amount=Decimal("10")),
        MasterCheckpoint(user_id=u1.id, title="Kural", description="x", checkpoint_type="rule"),
        Goal(user_id=u1.id, goal_type="cash_target", title="Acil fon", target_amount=Decimal("1000")),
        Goal(user_id=None, goal_type="cash_target", title="Global", target_amount=Decimal("5")),  # user_id NULL
    ])
    # u2'nin kaydı
    db_session.add(Account(user_id=u2.id, name="Kart", account_type="credit_card"))
    db_session.commit()
    return db_session, u1, u2


def test_backfill_personal_workspace_ve_atama(seeded):
    db, u1, u2 = seeded
    stats = run(db)
    assert stats["users"] == 2
    assert stats["workspaces_created"] == 2
    # her user'ın personal workspace'i owner membership'i var
    ws1 = db.query(Workspace).filter_by(owner_user_id=u1.id, is_personal=True).one()
    m = db.query(WorkspaceMembership).filter_by(workspace_id=ws1.id, user_id=u1.id).one()
    assert m.role == WorkspaceRole.owner
    # u1'in scoped kayıtları ws1'e atandı
    assert db.query(Account).filter_by(user_id=u1.id).one().workspace_id == ws1.id
    assert db.query(Transaction).filter_by(user_id=u1.id).one().workspace_id == ws1.id
    assert db.query(MasterCheckpoint).filter_by(user_id=u1.id).one().workspace_id == ws1.id
    # user_id dolu goal atandı, user_id NULL global goal ATANMADI
    assigned = db.query(Goal).filter_by(user_id=u1.id).one()
    assert assigned.workspace_id == ws1.id
    global_goal = db.query(Goal).filter_by(user_id=None).one()
    assert global_goal.workspace_id is None
    assert stats["goals_null_user_skipped"] == 1


def test_backfill_idempotent(seeded):
    db, u1, u2 = seeded
    run(db)
    ws_count_1 = db.query(Workspace).count()
    stats2 = run(db)  # ikinci koşu
    assert stats2["workspaces_created"] == 0
    assert stats2["rows_assigned"] == 0
    assert db.query(Workspace).count() == ws_count_1  # yeni workspace yaratılmadı


def test_backfill_user_izolasyonu(seeded):
    db, u1, u2 = seeded
    run(db)
    ws1 = db.query(Workspace).filter_by(owner_user_id=u1.id).one()
    ws2 = db.query(Workspace).filter_by(owner_user_id=u2.id).one()
    assert ws1.id != ws2.id
    # u2'nin account'u u2'nin workspace'ine (u1'e değil)
    assert db.query(Account).filter_by(user_id=u2.id).one().workspace_id == ws2.id
