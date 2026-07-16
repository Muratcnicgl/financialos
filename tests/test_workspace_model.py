"""
M40 (ADR-036) — Workspace + WorkspaceMembership model testleri + scoped tablolarda
workspace_id varlığı.
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    User, Workspace, WorkspaceMembership, WorkspaceRole,
    Account, Transaction, Goal, PersonalDebt, MasterCheckpoint,
    RecurringIncome, RecurringExpense, Envelope, WishlistItem,
    PendingAction, NetWorthSnapshot, DecisionJournal, CoachMemory, ApiCallLog,
)

_SCOPED = [Account, Transaction, Goal, PersonalDebt, MasterCheckpoint,
           RecurringIncome, RecurringExpense, Envelope, WishlistItem,
           PendingAction, NetWorthSnapshot, DecisionJournal]
_NOT_SCOPED = [CoachMemory, ApiCallLog]  # koç/kişisel — workspace'e taşınmaz


def test_scoped_tablolarda_workspace_id_var():
    for model in _SCOPED:
        assert "workspace_id" in model.__table__.columns, f"{model.__tablename__} workspace_id yok"


def test_kisisel_koc_tablolarinda_workspace_id_yok():
    for model in _NOT_SCOPED:
        assert "workspace_id" not in model.__table__.columns, \
            f"{model.__tablename__} workspace_id TAŞIMAMALI (gizlilik, ADR-036)"


def test_workspace_role_degerleri():
    assert [r.value for r in WorkspaceRole] == ["owner", "editor", "viewer"]


def test_workspace_ve_membership_yaratilir(db_session):
    u = User(name="murat")
    db_session.add(u)
    db_session.commit()
    ws = Workspace(owner_user_id=u.id, name="Kişisel", is_personal=True)
    db_session.add(ws)
    db_session.commit()
    m = WorkspaceMembership(workspace_id=ws.id, user_id=u.id, role=WorkspaceRole.owner)
    db_session.add(m)
    db_session.commit()
    assert ws.id is not None and m.role == WorkspaceRole.owner
    assert ws.memberships[0].user_id == u.id


def test_membership_unique_workspace_user(db_session):
    u = User(name="a")
    db_session.add(u)
    db_session.commit()
    ws = Workspace(owner_user_id=u.id, name="w")
    db_session.add(ws)
    db_session.commit()
    db_session.add(WorkspaceMembership(workspace_id=ws.id, user_id=u.id, role=WorkspaceRole.owner))
    db_session.commit()
    db_session.add(WorkspaceMembership(workspace_id=ws.id, user_id=u.id, role=WorkspaceRole.viewer))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_account_workspace_iliski(db_session):
    u = User(name="a")
    db_session.add(u)
    db_session.commit()
    ws = Workspace(owner_user_id=u.id, name="w")
    db_session.add(ws)
    db_session.commit()
    acc = Account(user_id=u.id, workspace_id=ws.id, name="Nakit", account_type="cash")
    db_session.add(acc)
    db_session.commit()
    assert acc.workspace_id == ws.id
