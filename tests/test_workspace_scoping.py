"""
M43 (ADR-036) — Endpoint workspace scoping testleri (köprü-desen).

Kanıt: X-Workspace-Id header'ı verildiğinde endpoint o workspace'in verisini döner
(user_id değil workspace_id filtresi). Header yoksa personal workspace'e düşer; personal
yoksa legacy user_id (mevcut testler bu yolla korunur). Her endpoint scoping'i buraya eklenir.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Workspace, WorkspaceMembership, WorkspaceRole, Account, Transaction,
    RecurringIncome, RecurringExpense, PersonalDebt, MasterCheckpoint,
    Envelope, WishlistItem, Goal,
)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def env(db):
    """u1: personal ws(1) + shared ws(2, u1 owner, u2 viewer). Her ws'de 1 account."""
    u1 = User(name="murat", email="m@x.com")
    u2 = User(name="es", email="es@x.com")
    db.add_all([u1, u2]); db.commit()
    personal = Workspace(owner_user_id=u1.id, name="Murat (Kişisel)", is_personal=True)
    shared = Workspace(owner_user_id=u1.id, name="Aile", is_personal=False)
    db.add_all([personal, shared]); db.commit()
    db.add_all([
        WorkspaceMembership(workspace_id=personal.id, user_id=u1.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=shared.id, user_id=u1.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=shared.id, user_id=u2.id, role=WorkspaceRole.viewer),
    ])
    db.add_all([
        Account(user_id=u1.id, workspace_id=personal.id, name="Kişisel Nakit", account_type="cash"),
        Account(user_id=u1.id, workspace_id=shared.id, name="Aile Nakit", account_type="cash"),
    ])
    db.commit()
    return {"u1": u1, "u2": u2, "personal": personal, "shared": shared}


@pytest.fixture
def client(db, env):
    app.dependency_overrides[get_db] = lambda: db
    state = {"user": env["u1"]}
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    c = TestClient(app)
    c._who = state
    yield c
    app.dependency_overrides.clear()


def _as(client, user):
    client._who["user"] = user


# ============================================================
# ACCOUNTS
# ============================================================

def test_accounts_personal_header_yoksa(client, env):
    """Header yoksa personal workspace → yalnız kişisel hesap."""
    r = client.get("/api/accounts")
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert names == ["Kişisel Nakit"]


def test_accounts_shared_header_ile(client, env):
    """X-Workspace-Id=shared → yalnız aile hesabı."""
    r = client.get("/api/accounts", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert names == ["Aile Nakit"]


def test_accounts_uye_olmayan_workspace_403(client, env):
    """u2 personal(1)'in üyesi değil → 403."""
    _as(client, env["u2"])
    r = client.get("/api/accounts", headers={"X-Workspace-Id": str(env["personal"].id)})
    assert r.status_code == 403


def test_accounts_create_aktif_workspace_e_baglanir(client, env, db):
    """Shared header ile yaratılan hesap workspace_id=shared alır."""
    r = client.post("/api/accounts", headers={"X-Workspace-Id": str(env["shared"].id)},
                    json={"name": "Yeni Aile Kart", "account_type": "credit_card"})
    assert r.status_code == 201
    acc = db.query(Account).filter_by(name="Yeni Aile Kart").one()
    assert acc.workspace_id == env["shared"].id


def test_accounts_viewer_shared_gorur(client, env):
    """viewer u2 shared workspace'in hesabını görebilir (okuma)."""
    _as(client, env["u2"])
    r = client.get("/api/accounts", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert r.status_code == 200
    assert [a["name"] for a in r.json()] == ["Aile Nakit"]


# ============================================================
# TRANSACTIONS
# ============================================================

@pytest.fixture
def txns(db, env):
    db.add_all([
        Transaction(user_id=env["u1"].id, workspace_id=env["personal"].id,
                    transaction_type="expense", amount=10, description="kişisel harcama"),
        Transaction(user_id=env["u1"].id, workspace_id=env["shared"].id,
                    transaction_type="expense", amount=20, description="aile harcama"),
    ])
    db.commit()
    return env


def test_transactions_personal_default(client, txns):
    r = client.get("/api/transactions")
    assert r.status_code == 200
    descs = [t["description"] for t in r.json()]
    assert descs == ["kişisel harcama"]


def test_transactions_shared_header(client, txns):
    r = client.get("/api/transactions", headers={"X-Workspace-Id": str(txns["shared"].id)})
    assert r.status_code == 200
    assert [t["description"] for t in r.json()] == ["aile harcama"]


def test_transactions_create_shared_baglanir(client, txns, db):
    # shared workspace'te bir nakit hesap var (Aile Nakit) → default hesap seçilir
    r = client.post("/api/transactions", headers={"X-Workspace-Id": str(txns["shared"].id)},
                    json={"transaction_type": "expense", "amount": 5, "description": "yeni aile"})
    assert r.status_code == 201, r.text
    t = db.query(Transaction).filter_by(description="yeni aile").one()
    assert t.workspace_id == txns["shared"].id


# ============================================================
# INCOMES / EXPENSES
# ============================================================

def test_incomes_scoping(client, env, db):
    db.add_all([
        RecurringIncome(user_id=env["u1"].id, workspace_id=env["personal"].id,
                        name="Kişisel Maaş", amount=100, day_of_month=1),
        RecurringIncome(user_id=env["u1"].id, workspace_id=env["shared"].id,
                        name="Aile Kira Geliri", amount=200, day_of_month=5),
    ])
    db.commit()
    r = client.get("/api/incomes")
    assert [i["name"] for i in r.json()] == ["Kişisel Maaş"]
    r2 = client.get("/api/incomes", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert [i["name"] for i in r2.json()] == ["Aile Kira Geliri"]


def test_income_create_workspace_baglanir(client, env, db):
    r = client.post("/api/incomes", headers={"X-Workspace-Id": str(env["shared"].id)},
                    json={"name": "Yeni Gelir", "amount": 50, "day_of_month": 10})
    assert r.status_code == 201
    assert db.query(RecurringIncome).filter_by(name="Yeni Gelir").one().workspace_id == env["shared"].id


def test_expenses_scoping(client, env, db):
    # gider account_id gerektirir → her ws'nin hesabını kullan
    pa = db.query(Account).filter_by(workspace_id=env["personal"].id).one()
    sa = db.query(Account).filter_by(workspace_id=env["shared"].id).one()
    db.add_all([
        RecurringExpense(user_id=env["u1"].id, workspace_id=env["personal"].id,
                         name="Kişisel Netflix", amount=10, account_id=pa.id, day_of_month=1),
        RecurringExpense(user_id=env["u1"].id, workspace_id=env["shared"].id,
                         name="Aile Fatura", amount=30, account_id=sa.id, day_of_month=5),
    ])
    db.commit()
    r = client.get("/api/expenses/recurring")
    assert [e["name"] for e in r.json()] == ["Kişisel Netflix"]
    r2 = client.get("/api/expenses/recurring", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert [e["name"] for e in r2.json()] == ["Aile Fatura"]


# ============================================================
# DEBTS / CHECKPOINTS
# ============================================================

def test_debts_scoping(client, env, db):
    db.add_all([
        PersonalDebt(user_id=env["u1"].id, workspace_id=env["personal"].id,
                     counterparty="Kişisel Efe", direction="receivable", amount=100),
        PersonalDebt(user_id=env["u1"].id, workspace_id=env["shared"].id,
                     counterparty="Aile Komşu", direction="payable", amount=50),
    ])
    db.commit()
    r = client.get("/api/debts")
    assert [d["counterparty"] for d in r.json()] == ["Kişisel Efe"]
    r2 = client.get("/api/debts", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert [d["counterparty"] for d in r2.json()] == ["Aile Komşu"]


def test_checkpoints_scoping(client, env, db):
    db.add_all([
        MasterCheckpoint(user_id=env["u1"].id, workspace_id=env["personal"].id,
                         title="Kişisel Kural", description="x", checkpoint_type="rule"),
        MasterCheckpoint(user_id=env["u1"].id, workspace_id=env["shared"].id,
                         title="Aile Kural", description="y", checkpoint_type="rule"),
    ])
    db.commit()
    r = client.get("/api/checkpoints")
    assert [c["title"] for c in r.json()] == ["Kişisel Kural"]
    r2 = client.get("/api/checkpoints", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert [c["title"] for c in r2.json()] == ["Aile Kural"]


# ============================================================
# ENVELOPES / WISHLIST
# ============================================================

def test_envelopes_scoping(client, env, db):
    db.add_all([
        Envelope(user_id=env["u1"].id, workspace_id=env["personal"].id,
                 category="kişisel-market", monthly_amount=100),
        Envelope(user_id=env["u1"].id, workspace_id=env["shared"].id,
                 category="aile-market", monthly_amount=300),
    ])
    db.commit()
    r = client.get("/api/envelopes")
    assert [e["category"] for e in r.json()["envelopes"]] == ["kişisel-market"]
    r2 = client.get("/api/envelopes", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert [e["category"] for e in r2.json()["envelopes"]] == ["aile-market"]


def test_wishlist_scoping(client, env, db):
    db.add_all([
        WishlistItem(user_id=env["u1"].id, workspace_id=env["personal"].id,
                     item="Kişisel Kulaklık", amount=100, status="pending"),
        WishlistItem(user_id=env["u1"].id, workspace_id=env["shared"].id,
                     item="Aile Fırın", amount=500, status="pending"),
    ])
    db.commit()
    r = client.get("/api/wishlist")
    assert [i["item"] for i in r.json()["items"]] == ["Kişisel Kulaklık"]
    r2 = client.get("/api/wishlist", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert [i["item"] for i in r2.json()["items"]] == ["Aile Fırın"]


# ============================================================
# GOALS
# ============================================================

def test_goals_scoping(client, env, db):
    from decimal import Decimal
    db.add_all([
        Goal(user_id=env["u1"].id, workspace_id=env["personal"].id,
             goal_type="cash_target", title="Kişisel Acil Fon", target_amount=Decimal("1000")),
        Goal(user_id=env["u1"].id, workspace_id=env["shared"].id,
             goal_type="cash_target", title="Aile Tatil", target_amount=Decimal("5000")),
    ])
    db.commit()
    r = client.get("/api/goals")
    assert [g["title"] for g in r.json()] == ["Kişisel Acil Fon"]
    r2 = client.get("/api/goals", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert [g["title"] for g in r2.json()] == ["Aile Tatil"]


def test_goal_create_workspace_baglanir(client, env, db):
    from decimal import Decimal
    r = client.post("/api/goals", headers={"X-Workspace-Id": str(env["shared"].id)},
                    json={"goal_type": "cash_target", "title": "Yeni Aile Hedef", "target_amount": "2000"})
    assert r.status_code == 201, r.text
    assert db.query(Goal).filter_by(title="Yeni Aile Hedef").one().workspace_id == env["shared"].id


# ============================================================
# COCKPIT (rules_engine, contextvar köprüsü)
# ============================================================

def test_cockpit_workspace_scoping(client, env, db):
    """Cockpit nakit_kasa aktif workspace'e göre değişir (rules_engine _scope)."""
    from decimal import Decimal
    # personal hesap (Kişisel Nakit) bakiye 1000, shared hesap (Aile Nakit) bakiye 7000
    db.query(Account).filter_by(workspace_id=env["personal"].id).update({"balance": Decimal("1000")})
    db.query(Account).filter_by(workspace_id=env["shared"].id).update({"balance": Decimal("7000")})
    db.commit()
    r_personal = client.get("/api/cockpit")
    assert r_personal.status_code == 200
    assert float(r_personal.json()["nakit_kasa"]) == 1000.0
    r_shared = client.get("/api/cockpit", headers={"X-Workspace-Id": str(env["shared"].id)})
    assert r_shared.status_code == 200
    assert float(r_shared.json()["nakit_kasa"]) == 7000.0
