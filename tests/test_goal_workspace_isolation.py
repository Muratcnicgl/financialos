"""
M72 (Wave-5, ADR-037) — Goal alt-sistemi workspace izolasyonu.

Kapsam iki katman:
1. GoalAllocation/GoalRule: user_id YOK, yalnız goal_id join. İzolasyon parent goal'ün
   workspace-scope'undan gelir (router her erişimde goal'ü scope_filter ile doğrular →
   test_workspace_scoping.py + burada dolaylı). Bu dosya asıl KAÇAĞI kanıtlar:
2. debt_freedom goal progress'i, goal_engine + debt_strategy.collect_debts üzerinden
   Account'ları sorgular. M43 bu iki dosyayı köprülememişti → `Account.user_id ==` ile
   TÜM workspace'lerin borcu karışıyordu (M72 fix). Test: shared ws goal'ü YALNIZ shared
   borcunu görür, personal ws'in kredisini görmez.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Workspace, WorkspaceMembership, WorkspaceRole, Account, AccountType, Goal,
)
from app.rules_engine import workspace_scope
from app.goal_engine import calculate_baseline_for_debt_freedom, refresh_goal


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def two_ws(db):
    """u1: personal ws (kredi 50000) + shared ws (kredi 20000). İki ws aynı user_id."""
    u1 = User(name="murat", email="m@x.com")
    db.add(u1); db.commit()
    personal = Workspace(owner_user_id=u1.id, name="Kişisel", is_personal=True)
    shared = Workspace(owner_user_id=u1.id, name="Aile", is_personal=False)
    db.add_all([personal, shared]); db.commit()
    db.add_all([
        WorkspaceMembership(workspace_id=personal.id, user_id=u1.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=shared.id, user_id=u1.id, role=WorkspaceRole.owner),
        Account(user_id=u1.id, workspace_id=personal.id, name="Kişisel Kredi",
                account_type=AccountType.loan, balance=50000, interest_rate=2.0),
        Account(user_id=u1.id, workspace_id=shared.id, name="Aile Kredi",
                account_type=AccountType.loan, balance=20000, interest_rate=2.0),
    ])
    db.commit()
    return {"u1": u1, "personal": personal, "shared": shared}


def test_baseline_yalniz_aktif_workspace_borcu(db, two_ws):
    """calculate_baseline shared kapsamında → 20000 (personal 50000 KARIŞMAZ)."""
    uid = two_ws["u1"].id
    with workspace_scope(two_ws["shared"].id):
        baseline_shared = calculate_baseline_for_debt_freedom(uid, db)
    with workspace_scope(two_ws["personal"].id):
        baseline_personal = calculate_baseline_for_debt_freedom(uid, db)
    assert baseline_shared == Decimal("20000")
    assert baseline_personal == Decimal("50000")
    # legacy (scope yok) → toplam 70000 (köprü fallback = user_id)
    assert calculate_baseline_for_debt_freedom(uid, db) == Decimal("70000")


def test_debt_freedom_goal_progress_izole(db, two_ws):
    """
    Shared ws'te debt_freedom goal: baseline 20000. Shared kredi 20000→15000 düşünce
    progress %25 olmalı. Personal kredinin (50000) HİÇ etkisi olmamalı (izolasyon).
    """
    uid = two_ws["u1"].id
    shared_id = two_ws["shared"].id

    with workspace_scope(shared_id):
        baseline = calculate_baseline_for_debt_freedom(uid, db)
    goal = Goal(user_id=uid, workspace_id=shared_id, goal_type="debt_freedom", target_amount=Decimal("0"),
                title="Aile borçsuz", status="active", baseline_amount=baseline)
    db.add(goal); db.commit()

    # Başlangıç: borç henüz azalmadı → %0
    refresh_goal(goal.id, db); db.commit(); db.refresh(goal)
    assert goal.progress_percent == Decimal("0.00")

    # Shared kredisini 20000→15000 azalt (5000 ödendi = baseline'ın %25'i)
    shared_loan = db.query(Account).filter_by(workspace_id=shared_id).first()
    shared_loan.balance = 15000
    db.commit()
    refresh_goal(goal.id, db); db.commit(); db.refresh(goal)
    assert goal.progress_percent == Decimal("25.00")
    assert goal.current_amount == Decimal("5000")


def test_personal_borc_degisimi_shared_goal_i_etkilemez(db, two_ws):
    """Personal kredi değişince shared debt_freedom goal progress'i DEĞİŞMEZ (izolasyon kanıtı)."""
    uid = two_ws["u1"].id
    shared_id = two_ws["shared"].id
    with workspace_scope(shared_id):
        baseline = calculate_baseline_for_debt_freedom(uid, db)
    goal = Goal(user_id=uid, workspace_id=shared_id, goal_type="debt_freedom", target_amount=Decimal("0"),
                title="Aile borçsuz", status="active", baseline_amount=baseline)
    db.add(goal); db.commit()
    refresh_goal(goal.id, db); db.commit(); db.refresh(goal)
    ilk_progress = goal.progress_percent

    # Personal krediyi tamamen kapat (50000→0) — shared goal'ü ETKİLEMEMELİ
    personal_loan = db.query(Account).filter_by(workspace_id=two_ws["personal"].id).first()
    personal_loan.balance = 0
    db.commit()
    refresh_goal(goal.id, db); db.commit(); db.refresh(goal)
    assert goal.progress_percent == ilk_progress  # değişmedi = izole
