"""
M79 — expenses.py + incomes.py router coverage.

RecurringExpense / RecurringIncome CRUD + trigger-due yollarının kapsamı:
create (başarı + validasyon + account sahiplik), update (başarı + account
doğrulama + 404), delete (başarı + 404), list (+ active_only), trigger-due
(due / not-due / dedup / cash-account yok).

Pattern: test_goals_ownership.py — in-memory SQLite (StaticPool), get_db /
get_current_user override. Workspace bağlamı YOK → scope_filter legacy user_id
yoluna düşer, require_write köprü-desenle atlanır (mevcut testlerle tutarlı).
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
from app.models import Base, User, Account, AccountType


# --- Deterministik "bugün": trigger-due day_of_month karşılaştırması için ---
_TODAY = date(2026, 7, 15)  # Temmuz = 31 gün; day<=15 due, day>15 not-due


class _FakeDate(date):
    @classmethod
    def today(cls):
        return _TODAY


@pytest.fixture(autouse=True)
def _freeze_today(monkeypatch):
    # BUG #197 (H4): "bugün" artık KULLANICININ saat diliminden türetiliyor
    # (`user_today`). Doğru dikiş orası — modül-düzeyi `date` yaması yerine onu dondururuz.
    monkeypatch.setattr("app.routers.expenses.date", _FakeDate)
    monkeypatch.setattr("app.routers.incomes.date", _FakeDate)
    monkeypatch.setattr("app.routers.expenses.user_today", lambda user: _TODAY)
    monkeypatch.setattr("app.routers.incomes.user_today", lambda user: _TODAY)


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add_all([User(id=1, name="murat"), User(id=2, name="baskasi")])
    s.flush()
    # user 1: bir nakit hesap (id=1). user 2: hesapsız (income cash-yok yolu).
    s.add(Account(id=1, user_id=1, name="Nakit Kasa", account_type=AccountType.cash, balance=10000))
    s.commit()
    yield s
    s.close()


def _client(db_session, uid=1):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, uid)
    return TestClient(app)


@pytest.fixture
def client(db_session):
    c = _client(db_session, 1)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


# ============================================================
# EXPENSES
# ============================================================

def _make_expense(client, **over):
    body = {"name": "Netflix", "amount": 150, "account_id": 1,
            "category": "abonelik", "day_of_month": 10}
    body.update(over)
    return client.post("/api/expenses/recurring", json=body)


def test_expense_create_success(client):
    r = _make_expense(client)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "Netflix"
    assert data["id"] > 0


def test_expense_create_invalid_amount(client):
    r = _make_expense(client, amount=0)  # FinansTutar gt=0 (SEC-032)
    assert r.status_code == 422, r.text


def test_expense_create_invalid_day(client):
    r = _make_expense(client, day_of_month=40)  # ge=1 le=31
    assert r.status_code == 422, r.text


def test_expense_create_nonexistent_account(client):
    r = _make_expense(client, account_id=9999)
    assert r.status_code == 404, r.text
    assert "Hesap bulunamadi" in r.text


def test_expense_list_and_active_only(client):
    _make_expense(client, name="Aktif", day_of_month=5)
    _make_expense(client, name="Pasif", day_of_month=6, is_active=False)
    r_all = client.get("/api/expenses/recurring")
    assert r_all.status_code == 200
    assert len(r_all.json()) == 2
    r_active = client.get("/api/expenses/recurring", params={"active_only": True})
    assert r_active.status_code == 200
    names = [e["name"] for e in r_active.json()]
    assert names == ["Aktif"]


def test_expense_update_success(client):
    eid = _make_expense(client).json()["id"]
    r = client.put(f"/api/expenses/recurring/{eid}", json={"name": "Spotify", "amount": 60})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Spotify"


def test_expense_update_account_ownership_404(client):
    eid = _make_expense(client).json()["id"]
    r = client.put(f"/api/expenses/recurring/{eid}", json={"account_id": 9999})
    assert r.status_code == 404, r.text
    assert "Hedef hesap" in r.text


def test_expense_update_nonexistent(client):
    r = client.put("/api/expenses/recurring/9999", json={"name": "yok"})
    assert r.status_code == 404, r.text


def test_expense_delete_success(client):
    eid = _make_expense(client).json()["id"]
    r = client.delete(f"/api/expenses/recurring/{eid}")
    assert r.status_code == 204, r.text
    assert client.get("/api/expenses/recurring").json() == []


def test_expense_delete_nonexistent(client):
    r = client.delete("/api/expenses/recurring/9999")
    assert r.status_code == 404, r.text


def test_expense_trigger_due(client):
    _make_expense(client, name="Kira", day_of_month=10)  # 10 <= 15 → due
    r = client.post("/api/expenses/recurring/trigger-due")
    assert r.status_code == 200, r.text
    triggered = r.json()["triggered"]
    assert len(triggered) == 1
    assert triggered[0]["action_type"] == "add_transaction"
    assert triggered[0]["payload"]["transaction_type"] == "expense"


def test_expense_trigger_not_due(client):
    _make_expense(client, name="Ileri", day_of_month=25)  # 25 > 15 → not due
    r = client.post("/api/expenses/recurring/trigger-due")
    assert r.status_code == 200, r.text
    assert r.json()["triggered"] == []


def test_expense_trigger_dedup(client):
    _make_expense(client, name="Kira", day_of_month=10)
    first = client.post("/api/expenses/recurring/trigger-due").json()["triggered"]
    assert len(first) == 1
    # ikinci çağrı: aynı ay pending zaten var → tekrar üretmez
    second = client.post("/api/expenses/recurring/trigger-due").json()["triggered"]
    assert second == []


def test_expense_trigger_skips_inactive(client):
    _make_expense(client, name="Pasif", day_of_month=10, is_active=False)
    r = client.post("/api/expenses/recurring/trigger-due")
    assert r.json()["triggered"] == []


def test_expense_trigger_skips_already_triggered_this_month(client, db_session):
    from app.models import RecurringExpense
    eid = _make_expense(client, name="Kira", day_of_month=10).json()["id"]
    # bu ay zaten execute'te işaretlenmiş → tetiklenmez (last_triggered dedup)
    db_session.get(RecurringExpense, eid).last_triggered_year_month = "2026-07"
    db_session.commit()
    r = client.post("/api/expenses/recurring/trigger-due")
    assert r.json()["triggered"] == []


# ============================================================
# INCOMES
# ============================================================

def _make_income(client, **over):
    body = {"name": "Maas", "amount": 50000, "day_of_month": 10}
    body.update(over)
    return client.post("/api/incomes", json=body)


def test_income_create_success(client):
    r = _make_income(client)
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Maas"


def test_income_create_invalid_amount(client):
    r = _make_income(client, amount=-5)  # gt=0
    assert r.status_code == 422, r.text


def test_income_create_invalid_day(client):
    r = _make_income(client, day_of_month=0)  # ge=1
    assert r.status_code == 422, r.text


def test_income_list_and_active_only(client):
    _make_income(client, name="Aktif", day_of_month=5)
    _make_income(client, name="Pasif", day_of_month=6, is_active=False)
    assert len(client.get("/api/incomes").json()) == 2
    active = client.get("/api/incomes", params={"active_only": True}).json()
    assert [i["name"] for i in active] == ["Aktif"]


def test_income_update_success(client):
    iid = _make_income(client).json()["id"]
    r = client.put(f"/api/incomes/{iid}", json={"is_active": False, "amount": 42000})
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False


def test_income_update_nonexistent(client):
    r = client.put("/api/incomes/9999", json={"name": "yok"})
    assert r.status_code == 404, r.text


def test_income_delete_success(client):
    iid = _make_income(client).json()["id"]
    r = client.delete(f"/api/incomes/{iid}")
    assert r.status_code == 204, r.text
    assert client.get("/api/incomes").json() == []


def test_income_delete_nonexistent(client):
    r = client.delete("/api/incomes/9999")
    assert r.status_code == 404, r.text


def test_income_trigger_due(client):
    _make_income(client, name="Maas", day_of_month=10)  # due, user1 nakit hesabı var
    r = client.post("/api/incomes/trigger-due")
    assert r.status_code == 200, r.text
    triggered = r.json()["triggered"]
    assert len(triggered) == 1
    assert triggered[0]["payload"]["transaction_type"] == "income"


def test_income_trigger_not_due(client):
    _make_income(client, name="Ileri", day_of_month=25)  # not due
    r = client.post("/api/incomes/trigger-due")
    assert r.json()["triggered"] == []


def test_income_trigger_dedup(client):
    _make_income(client, name="Maas", day_of_month=10)
    assert len(client.post("/api/incomes/trigger-due").json()["triggered"]) == 1
    assert client.post("/api/incomes/trigger-due").json()["triggered"] == []


def test_expense_trigger_propose_error_is_swallowed(client, monkeypatch):
    # propose_action patlarsa endpoint çökmez, o kalem atlanır (log + devam).
    def _boom(*a, **k):
        raise RuntimeError("patladi")
    monkeypatch.setattr("app.action_executor.propose_action", _boom)
    _make_expense(client, name="Kira", day_of_month=10)
    r = client.post("/api/expenses/recurring/trigger-due")
    assert r.status_code == 200
    assert r.json()["triggered"] == []


def test_income_trigger_propose_error_is_swallowed(client, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("patladi")
    monkeypatch.setattr("app.action_executor.propose_action", _boom)
    _make_income(client, name="Maas", day_of_month=10)
    r = client.post("/api/incomes/trigger-due")
    assert r.status_code == 200
    assert r.json()["triggered"] == []


def test_income_trigger_skips_already_triggered_this_month(client, db_session):
    from app.models import RecurringIncome
    iid = _make_income(client, name="Maas", day_of_month=10).json()["id"]
    db_session.get(RecurringIncome, iid).last_triggered_year_month = "2026-07"
    db_session.commit()
    r = client.post("/api/incomes/trigger-due")
    assert r.json()["triggered"] == []


def test_income_trigger_no_cash_account(db_session):
    # user 2: hesabı yok → cash_acc None → erken boş dönüş (line 146).
    try:
        c2 = _client(db_session, 2)
        r = c2.post("/api/incomes", json={"name": "Kira", "amount": 3000, "day_of_month": 10})
        assert r.status_code == 201, r.text
        trig = c2.post("/api/incomes/trigger-due")
        assert trig.status_code == 200, trig.text
        assert trig.json()["triggered"] == []
    finally:
        app.dependency_overrides.clear()
