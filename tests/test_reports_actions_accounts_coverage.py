"""
M79 — reports / actions / accounts router coverage genişletme.

Kapsanmayan dalları hedefler (hata/branch/boş-veri/filtre/sahiplik):
- reports.py: income dalı, attribution/real-net-worth None dalları, upcoming-cashflow
  içindeki alacak/borç etiketleri + loan taksitleri + recurring gelir/gider tekrarları,
  monthly-summary.
- actions.py: pending list, reject 404, edit (success/404), history (filtreli/filtresiz),
  _should_reflect branch'leri.
- accounts.py: list filtre, create investment auto-balance, get 404/success, update
  404/smart-balance/price-changed, delete 404/emanet-403/bağımlı-409.

Pattern: in-memory SQLite StaticPool + get_db/get_current_user override, iki kullanıcı
(id=1/2), try/finally overrides temizliği (test_goals_ownership.py deseni).
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, Transaction, TransactionType,
    PersonalDebt, DebtDirection, RecurringIncome, RecurringExpense,
    NetWorthSnapshot, PendingAction, ActionStatus, ActionHistory, ActionSource,
)
from app.routers.actions import _should_reflect


# ============================================================
# FIXTURE + YARDIMCILAR
# ============================================================

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


def _client(db_session, uid=1):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, uid)
    return TestClient(app)


def _cash(db, uid=1, balance=5000.0, name="Enpara"):
    a = Account(user_id=uid, name=name, account_type=AccountType.cash, balance=balance)
    db.add(a); db.commit(); db.refresh(a)
    return a


def _pending(db, uid, payload, action_type="add_transaction",
             status=ActionStatus.pending, summary="t"):
    p = PendingAction(user_id=uid, action_type=action_type,
                      payload=json.dumps(payload), summary=summary, status=status)
    db.add(p); db.commit(); db.refresh(p)
    return p


# ============================================================
# REPORTS — category-breakdown
# ============================================================

def test_category_breakdown_income_dali(db_session):
    """reports.py:78 — type=income dalı (gelir filtresi)."""
    try:
        c = _client(db_session)
        db_session.add(Transaction(user_id=1, transaction_type=TransactionType.income,
                                   amount=1500, category="maas",
                                   transaction_date=date.today() - timedelta(days=2)))
        db_session.commit()
        body = c.get("/api/reports/category-breakdown?type=income").json()
        assert body["type"] == "income"
        assert body["grand_total"] == 1500.0
        assert body["items"][0]["category"] == "maas"
    finally:
        app.dependency_overrides.clear()


def test_category_breakdown_bos_veri_yuzde_sifir(db_session):
    """grand_total=0 → percentage 0.0 dalı (bölme koruması)."""
    try:
        c = _client(db_session)
        body = c.get("/api/reports/category-breakdown?type=expense").json()
        assert body["grand_total"] == 0.0
        assert body["items"] == []
    finally:
        app.dependency_overrides.clear()


def test_category_breakdown_both_mode_yon_etiketi(db_session):
    """reports.py:80,96-97 — both modu: gelir/gider .in_ filtresi + yön etiketi."""
    try:
        c = _client(db_session)
        db_session.add_all([
            Transaction(user_id=1, transaction_type=TransactionType.income, amount=1000,
                        category="bonus", transaction_date=date.today() - timedelta(days=1)),
            Transaction(user_id=1, transaction_type=TransactionType.expense, amount=300,
                        category="market", transaction_date=date.today() - timedelta(days=1)),
        ])
        db_session.commit()
        body = c.get("/api/reports/category-breakdown?type=both").json()
        labels = [i["category"] for i in body["items"]]
        assert any("(gelir)" in l for l in labels)
        assert any("(gider)" in l for l in labels)
    finally:
        app.dependency_overrides.clear()


# ============================================================
# REPORTS — net-worth-trend
# ============================================================

def test_net_worth_trend_bos_ve_dolu(db_session):
    """reports.py:134-153 — boş liste + dolu snapshot serisi."""
    try:
        c = _client(db_session)
        assert c.get("/api/reports/net-worth-trend?days=30").json()["items"] == []
        db_session.add(NetWorthSnapshot(user_id=1, snapshot_date=date.today(),
                                        net_worth_seen=5000, net_worth_full=6000,
                                        cash=5000, card_debt=0, loan_debt=0,
                                        investment_value=1200, receivables=1000))
        db_session.commit()
        body = c.get("/api/reports/net-worth-trend?days=30").json()
        assert len(body["items"]) == 1
        assert body["items"][0]["net_worth_seen"] == 5000.0
        assert body["items"][0]["investment_value"] == 1200.0
    finally:
        app.dependency_overrides.clear()


# ============================================================
# REPORTS — net-worth-attribution / real-net-worth (None dalları)
# ============================================================

def test_attribution_yetersiz_snapshot_available_false(db_session):
    """reports.py:170 — snapshot yok → {available: False}."""
    try:
        c = _client(db_session)
        assert c.get("/api/reports/net-worth-attribution").json() == {"available": False}
    finally:
        app.dependency_overrides.clear()


def test_attribution_available_true(db_session):
    """reports.py:170 diğer dal — iki snapshot varsa available True + sürücüler."""
    try:
        c = _client(db_session)
        today = date.today()
        ay_basi = date(today.year, today.month, 1)
        onceki = ay_basi - timedelta(days=5)
        db_session.add_all([
            NetWorthSnapshot(user_id=1, snapshot_date=onceki, net_worth_seen=1000,
                             net_worth_full=1000, cash=1000, card_debt=0, loan_debt=0,
                             investment_value=0, receivables=0),
            NetWorthSnapshot(user_id=1, snapshot_date=today, net_worth_seen=2000,
                             net_worth_full=2000, cash=2000, card_debt=0, loan_debt=0,
                             investment_value=0, receivables=0),
        ])
        db_session.commit()
        body = c.get("/api/reports/net-worth-attribution").json()
        assert body["available"] is True
        assert "surucureler" in body
    finally:
        app.dependency_overrides.clear()


def test_real_net_worth_yetersiz_available_false(db_session):
    """reports.py:186 — yeterli snapshot yok → {available: False}."""
    try:
        c = _client(db_session)
        assert c.get("/api/reports/real-net-worth").json() == {"available": False}
    finally:
        app.dependency_overrides.clear()


def test_real_net_worth_available_true(db_session):
    """reports.py:187 — iki tarihli snapshot → reel net değer hesaplanır."""
    try:
        c = _client(db_session)
        today = date.today()
        db_session.add_all([
            NetWorthSnapshot(user_id=1, snapshot_date=today - timedelta(days=90),
                             net_worth_seen=10000, net_worth_full=10000, cash=10000,
                             card_debt=0, loan_debt=0, investment_value=0, receivables=0),
            NetWorthSnapshot(user_id=1, snapshot_date=today,
                             net_worth_seen=11000, net_worth_full=11000, cash=11000,
                             card_debt=0, loan_debt=0, investment_value=0, receivables=0),
        ])
        db_session.commit()
        body = c.get("/api/reports/real-net-worth").json()
        assert body["available"] is True
        assert "reel_net" in body and "enflasyon_etkisi" in body
    finally:
        app.dependency_overrides.clear()


# ============================================================
# REPORTS — upcoming-cashflow (alacak/borç/loan/recurring dalları)
# ============================================================

def test_upcoming_cashflow_bos(db_session):
    try:
        c = _client(db_session)
        body = c.get("/api/reports/upcoming-cashflow?days=30").json()
        assert body["items"] == []
        assert body["summary"]["items_count"] == 0
        assert body["summary"]["net_flow"] == 0
    finally:
        app.dependency_overrides.clear()


def test_upcoming_cashflow_alacak_ve_borc(db_session):
    """reports.py:230-231, 242-243 — receivable + payable etiketleri (açıklamalı)."""
    try:
        c = _client(db_session)
        soon = date.today() + timedelta(days=5)
        db_session.add_all([
            PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                         amount=1000, description="tatil", due_date=soon, is_paid=False),
            PersonalDebt(user_id=1, counterparty="Banka", direction=DebtDirection.payable,
                         amount=500, due_date=soon, is_paid=False),
            # ödenmiş → dahil edilmemeli
            PersonalDebt(user_id=1, counterparty="Eski", direction=DebtDirection.receivable,
                         amount=999, due_date=soon, is_paid=True),
        ])
        db_session.commit()
        body = c.get("/api/reports/upcoming-cashflow?days=30").json()
        types = {i["type"] for i in body["items"]}
        assert "receivable" in types and "payable" in types
        rec = [i for i in body["items"] if i["type"] == "receivable"][0]
        assert "tatil" in rec["label"]  # açıklama etiketi
        pay = [i for i in body["items"] if i["type"] == "payable"][0]
        assert pay["amount"] < 0
        assert body["summary"]["total_receivable"] == 1000.0
        assert body["summary"]["total_payable"] == -500.0
    finally:
        app.dependency_overrides.clear()


def test_upcoming_cashflow_loan_taksitleri(db_session):
    """reports.py:257-270 — loan hesabı için ufuk boyunca aylık taksitler."""
    try:
        c = _client(db_session)
        db_session.add(Account(
            user_id=1, name="Ihtiyac Kredisi", account_type=AccountType.loan,
            balance=-10000, monthly_payment=1000,
            remaining_installments=6, next_payment_date=date.today() + timedelta(days=3),
        ))
        db_session.commit()
        body = c.get("/api/reports/upcoming-cashflow?days=120").json()
        loan_items = [i for i in body["items"] if i["source"] == "loan"]
        assert len(loan_items) >= 2  # 120 günde birden fazla taksit
        assert all(i["amount"] == -1000 for i in loan_items)
    finally:
        app.dependency_overrides.clear()


def test_upcoming_cashflow_loan_sifir_odeme_atlanir(db_session):
    """reports.py:258-259 — monthly_payment<=0 loan atlanır (continue)."""
    try:
        c = _client(db_session)
        db_session.add(Account(
            user_id=1, name="Sifir Kredi", account_type=AccountType.loan,
            balance=0, monthly_payment=0,
            remaining_installments=6, next_payment_date=date.today() + timedelta(days=3),
        ))
        db_session.commit()
        body = c.get("/api/reports/upcoming-cashflow?days=120").json()
        assert [i for i in body["items"] if i["source"] == "loan"] == []
    finally:
        app.dependency_overrides.clear()


def test_upcoming_cashflow_recurring_gelir_gider(db_session):
    """reports.py:277-278, 286-287 + _next_occurrences (196-204)."""
    try:
        c = _client(db_session)
        acc = _cash(db_session)
        db_session.add_all([
            RecurringIncome(user_id=1, name="Maas", amount=20000,
                            day_of_month=15, is_active=True),
            RecurringExpense(user_id=1, name="Kira", amount=8000, account_id=acc.id,
                             day_of_month=1, is_active=True),
            # pasif → dahil edilmemeli
            RecurringIncome(user_id=1, name="Eski", amount=1, day_of_month=10, is_active=False),
        ])
        db_session.commit()
        body = c.get("/api/reports/upcoming-cashflow?days=90").json()
        sources = {i["source"] for i in body["items"]}
        assert "income" in sources
        assert "recurring_expense" in sources
        inc = [i for i in body["items"] if i["source"] == "income"]
        assert all(i["amount"] == 20000 for i in inc)
        exp = [i for i in body["items"] if i["source"] == "recurring_expense"]
        assert all(i["amount"] == -8000 for i in exp)
    finally:
        app.dependency_overrides.clear()


# ============================================================
# REPORTS — monthly-summary
# ============================================================

def test_monthly_summary_varsayilan_ay(db_session):
    try:
        c = _client(db_session)
        db_session.add(Transaction(user_id=1, transaction_type=TransactionType.expense,
                                   amount=250, category="market",
                                   transaction_date=date.today()))
        db_session.commit()
        body = c.get("/api/reports/monthly-summary").json()
        assert "current" in body and "trend" in body
        assert body["period"]["year"] == date.today().year
    finally:
        app.dependency_overrides.clear()


def test_monthly_summary_belirli_ay_parametreli(db_session):
    try:
        c = _client(db_session)
        body = c.get("/api/reports/monthly-summary?year=2026&month=3").json()
        assert body["period"]["year"] == 2026
        assert body["period"]["month"] == 3
    finally:
        app.dependency_overrides.clear()


# ============================================================
# ACTIONS — pending list / reject / edit / history
# ============================================================

def test_pending_list_sadece_pending(db_session):
    """actions.py:217-227 — pending listesi (executed hariç)."""
    try:
        acc = _cash(db_session)
        _pending(db_session, 1, {"transaction_type": "expense", "amount": 100.0,
                                 "account_id": acc.id})
        _pending(db_session, 1, {"transaction_type": "expense", "amount": 50.0},
                 status=ActionStatus.executed)
        r = _client(db_session).get("/api/actions/pending")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["status"] == "pending"
    finally:
        app.dependency_overrides.clear()


def test_approve_uygular_ve_history_yazar(db_session):
    """actions.py:241-331 — approve: execute + snapshot + ActionHistory.
    amount<100 gider → reflection background eklenmez (dış çağrı yok)."""
    try:
        acc = _cash(db_session)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 50.0,
                                     "account_id": acc.id, "auto_update_balance": True,
                                     "category": "ulasim"})
        r = _client(db_session).post(f"/api/actions/{p.id}/approve")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["action_type"] == "add_transaction"
        db_session.refresh(acc); db_session.refresh(p)
        assert acc.balance == 4950.0
        assert p.status == ActionStatus.executed
        assert db_session.query(ActionHistory).count() == 1
    finally:
        app.dependency_overrides.clear()


def test_approve_reflection_background_tetiklenir(db_session, monkeypatch):
    """actions.py:308-319 + _run_reflection (79-120) — 100 TL üstü gider reflection
    background task ekler. GROQ_API_KEY boş → _run_reflection erken döner (dış çağrı yok)."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    try:
        acc = _cash(db_session)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 250.0,
                                     "account_id": acc.id, "auto_update_balance": True,
                                     "category": "market"})
        r = _client(db_session).post(f"/api/actions/{p.id}/approve")
        assert r.status_code == 200
        db_session.refresh(p)
        assert p.status == ActionStatus.executed
    finally:
        app.dependency_overrides.clear()


def test_approve_reflection_groq_loop_calisir(db_session, monkeypatch):
    """actions.py:122-146 — GROQ_API_KEY var + sahte GroqProvider (boş tool_calls) →
    model döngüsü çalışır, insight üretmeden döner (dış ağ çağrısı yok)."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    class _FakeResp:
        tool_calls = [{
            "name": "save_insight",
            "input": {"content": "market harcaması haftalık tekrar ediyor",
                      "category": "pattern", "priority": "normal",
                      "dedup_key": "market_expense_weekly"},
        }]

    class _FakeGroq:
        def __init__(self, *a, **k):
            pass

        def chat(self, *a, **k):
            return _FakeResp()

    import app.coach as coach_mod
    monkeypatch.setattr(coach_mod, "GroqProvider", _FakeGroq)
    try:
        acc = _cash(db_session)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 300.0,
                                     "account_id": acc.id, "auto_update_balance": True,
                                     "category": "market"})
        r = _client(db_session).post(f"/api/actions/{p.id}/approve")
        assert r.status_code == 200
        db_session.refresh(p)
        assert p.status == ActionStatus.executed
    finally:
        app.dependency_overrides.clear()


def test_approve_olmayan_404(db_session):
    """actions.py:258-259 — olmayan aksiyon 404."""
    try:
        assert _client(db_session).post("/api/actions/99999/approve").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_approve_zaten_executed_422(db_session):
    """actions.py:263-267 — execute başarısız (zaten executed) → 422."""
    try:
        acc = _cash(db_session)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 50.0,
                                     "account_id": acc.id, "auto_update_balance": True},
                     status=ActionStatus.executed)
        r = _client(db_session).post(f"/api/actions/{p.id}/approve")
        assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_approve_basarisiz_is_mantigi_422(db_session):
    """actions.py:263-267 — handler success=False (olmayan hesap) → 422."""
    try:
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 50.0,
                                     "account_id": 99999, "auto_update_balance": True})
        r = _client(db_session).post(f"/api/actions/{p.id}/approve")
        assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_approve_baska_kullanici_404(db_session):
    """approve sahiplik: user 2, user 1'in aksiyonunu onaylayamaz."""
    try:
        acc = _cash(db_session, uid=1)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 50.0,
                                     "account_id": acc.id, "auto_update_balance": True})
    finally:
        app.dependency_overrides.clear()
    try:
        assert _client(db_session, uid=2).post(f"/api/actions/{p.id}/approve").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_reject_olmayan_action_404(db_session):
    """actions.py:346 — reject_pending_action None → 404."""
    try:
        r = _client(db_session).post("/api/actions/99999/reject", json={"reason": "x"})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_reject_zaten_executed_404(db_session):
    """reject: status != pending → success False → 404."""
    try:
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 100.0},
                     status=ActionStatus.executed)
        r = _client(db_session).post(f"/api/actions/{p.id}/reject")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_reject_body_none_calisir(db_session):
    """reject body olmadan (RejectRequest None dalı)."""
    try:
        acc = _cash(db_session)
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 100.0,
                                     "account_id": acc.id})
        r = _client(db_session).post(f"/api/actions/{p.id}/reject")
        assert r.status_code == 200
        db_session.refresh(p)
        assert p.status == ActionStatus.rejected
    finally:
        app.dependency_overrides.clear()


def test_edit_action_basarili(db_session):
    """actions.py:359-383 — payload+summary güncelle (kart olmayan kategori: dokunulmaz)."""
    try:
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 100.0,
                                     "category": "ulasim"})
        new = {"payload": {"transaction_type": "expense", "amount": 250.0,
                           "category": "ulasim"},
               "summary": "duzeltildi"}
        r = _client(db_session).post(f"/api/actions/{p.id}/edit", json=new)
        assert r.status_code == 200
        assert r.json()["summary"] == "duzeltildi"
        db_session.refresh(p)
        assert json.loads(p.payload)["amount"] == 250.0
    finally:
        app.dependency_overrides.clear()


def test_edit_action_olmayan_404(db_session):
    """actions.py:368-369 — olmayan/edit-edilemez aksiyon → 404."""
    try:
        r = _client(db_session).post("/api/actions/99999/edit",
                                     json={"payload": {}, "summary": "x"})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_edit_action_executed_olan_404(db_session):
    """edit: status pending olmayan → filtre eşleşmez → 404."""
    try:
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 100.0},
                     status=ActionStatus.executed)
        r = _client(db_session).post(f"/api/actions/{p.id}/edit",
                                     json={"payload": {"amount": 5}, "summary": "y"})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_edit_baska_kullanici_404(db_session):
    """edit sahiplik: user 2 user 1'in aksiyonunu düzenleyemez."""
    try:
        p = _pending(db_session, 1, {"transaction_type": "expense", "amount": 100.0,
                                     "category": "ulasim"})
    finally:
        app.dependency_overrides.clear()
    try:
        r = _client(db_session, uid=2).post(f"/api/actions/{p.id}/edit",
                                            json={"payload": {"amount": 5}, "summary": "y"})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_history_filtresiz(db_session):
    """actions.py:394-402 — tüm geçmiş."""
    try:
        db_session.add_all([
            ActionHistory(user_id=1, action_type="add_transaction", payload="{}",
                          summary="a", source=ActionSource.coach, success=True),
            ActionHistory(user_id=1, action_type="sell_investment", payload="{}",
                          summary="b", source=ActionSource.user, success=True),
        ])
        db_session.commit()
        r = _client(db_session).get("/api/actions/history")
        assert r.status_code == 200
        assert len(r.json()) == 2
    finally:
        app.dependency_overrides.clear()


def test_history_action_type_filtreli(db_session):
    """actions.py:398-399 — action_type filtresi dalı."""
    try:
        db_session.add_all([
            ActionHistory(user_id=1, action_type="add_transaction", payload="{}",
                          summary="a", source=ActionSource.coach, success=True),
            ActionHistory(user_id=1, action_type="sell_investment", payload="{}",
                          summary="b", source=ActionSource.user, success=True),
        ])
        db_session.commit()
        r = _client(db_session).get("/api/actions/history?action_type=sell_investment")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["action_type"] == "sell_investment"
    finally:
        app.dependency_overrides.clear()


def test_history_sadece_kendi_kullanicisi(db_session):
    """history sahiplik: user 2 kayıtları user 1'e görünmez."""
    try:
        db_session.add(ActionHistory(user_id=2, action_type="add_transaction", payload="{}",
                                     summary="baskasi", source=ActionSource.user, success=True))
        db_session.commit()
        r = _client(db_session, uid=1).get("/api/actions/history")
        assert r.status_code == 200
        assert r.json() == []
    finally:
        app.dependency_overrides.clear()


# --- _should_reflect branch coverage (actions.py:57-64) ---

def test_should_reflect_bilinmeyen_tip_false():
    """actions.py:58 — reflection tipi değil → False."""
    assert _should_reflect("update_account_balance", {"amount": 500}) is False


def test_should_reflect_gelir_false():
    """actions.py:60-61 — add_transaction income → False."""
    assert _should_reflect("add_transaction",
                           {"transaction_type": "income", "amount": 5000}) is False


def test_should_reflect_dusuk_tutar_false():
    """actions.py:62-63 — 100 TL altı harcama → False."""
    assert _should_reflect("add_transaction",
                           {"transaction_type": "expense", "amount": 50}) is False


def test_should_reflect_yuksek_harcama_true():
    """actions.py:64 — 100 TL üstü gider → True."""
    assert _should_reflect("add_transaction",
                           {"transaction_type": "expense", "amount": 250}) is True


# ============================================================
# ACCOUNTS — list / create / get / update / delete
# ============================================================

def test_list_accounts_type_filtresi(db_session):
    """accounts.py:107 — account_type filtresi dalı."""
    try:
        _cash(db_session, name="Nakit")
        db_session.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card,
                               balance=0, credit_limit=10000))
        db_session.commit()
        c = _client(db_session)
        hepsi = c.get("/api/accounts").json()
        assert len(hepsi) == 2
        sadece_nakit = c.get("/api/accounts?account_type=cash").json()
        assert len(sadece_nakit) == 1
        assert sadece_nakit[0]["account_type"] == "cash"
    finally:
        app.dependency_overrides.clear()


def test_create_investment_auto_balance(db_session):
    """accounts.py:125,129 — yatırım lot*fiyat auto-balance + last_price_update."""
    try:
        c = _client(db_session)
        r = c.post("/api/accounts", json={
            "name": "TLY Fonu", "account_type": "investment",
            "lot_count": 100, "current_price": 5.0, "fund_code": "TLY",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["balance"] == 500.0  # 100 * 5
        assert body["last_price_update"] is not None
    finally:
        app.dependency_overrides.clear()


def test_create_account_validasyon_hatasi_422(db_session):
    """boş name (min_length=1) → 422."""
    try:
        c = _client(db_session)
        r = c.post("/api/accounts", json={"name": "", "account_type": "cash"})
        assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_get_account_olmayan_404(db_session):
    """accounts.py:149-150 — olmayan hesap 404."""
    try:
        assert _client(db_session).get("/api/accounts/99999").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_account_basarili(db_session):
    """accounts.py:145-151 — sahip erişebilir."""
    try:
        acc = _cash(db_session)
        r = _client(db_session).get(f"/api/accounts/{acc.id}")
        assert r.status_code == 200
        assert r.json()["name"] == "Enpara"
    finally:
        app.dependency_overrides.clear()


def test_get_account_baska_kullanici_404(db_session):
    """sahiplik: user 2, user 1'in hesabını göremez."""
    try:
        acc = _cash(db_session, uid=1)
    finally:
        app.dependency_overrides.clear()
    try:
        assert _client(db_session, uid=2).get(f"/api/accounts/{acc.id}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_update_account_olmayan_404(db_session):
    """accounts.py:177-178 — olmayan hesap update 404."""
    try:
        r = _client(db_session).put("/api/accounts/99999", json={"balance": 100})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_update_account_basit_alan(db_session):
    """accounts.py:180-185 — sadece gönderilen alan güncellenir."""
    try:
        acc = _cash(db_session)
        r = _client(db_session).put(f"/api/accounts/{acc.id}",
                                    json={"balance": 7500, "notes": "guncel"})
        assert r.status_code == 200
        assert r.json()["balance"] == 7500.0
        assert r.json()["notes"] == "guncel"
    finally:
        app.dependency_overrides.clear()


def test_update_investment_akilli_bakiye(db_session):
    """accounts.py:188-193 — yatırım lot değişince balance = lot*fiyat (balance verilmedi)."""
    try:
        inv = Account(user_id=1, name="Fon", account_type=AccountType.investment,
                      balance=500, lot_count=100, current_price=5.0)
        db_session.add(inv); db_session.commit(); db_session.refresh(inv)
        r = _client(db_session).put(f"/api/accounts/{inv.id}", json={"lot_count": 200})
        assert r.status_code == 200
        assert r.json()["balance"] == 1000.0  # 200 * 5
    finally:
        app.dependency_overrides.clear()


def test_update_price_changed_timestamp(db_session):
    """accounts.py:196-197 — current_price değişince last_price_update yazılır."""
    try:
        inv = Account(user_id=1, name="Fon2", account_type=AccountType.investment,
                      balance=500, lot_count=100, current_price=5.0)
        db_session.add(inv); db_session.commit(); db_session.refresh(inv)
        r = _client(db_session).put(f"/api/accounts/{inv.id}", json={"current_price": 6.0})
        assert r.status_code == 200
        body = r.json()
        assert body["last_price_update"] is not None
        assert body["balance"] == 600.0  # akıllı bakiye (lot 100 * 6)
    finally:
        app.dependency_overrides.clear()


def test_update_investment_balance_acikca_verilince_akilli_devre_disi(db_session):
    """accounts.py:181,188 — kullanıcı balance açıkça verirse akıllı bakiye devre dışı."""
    try:
        inv = Account(user_id=1, name="Fon3", account_type=AccountType.investment,
                      balance=500, lot_count=100, current_price=5.0)
        db_session.add(inv); db_session.commit(); db_session.refresh(inv)
        r = _client(db_session).put(f"/api/accounts/{inv.id}",
                                    json={"lot_count": 200, "balance": 9999})
        assert r.status_code == 200
        assert r.json()["balance"] == 9999.0  # açık öncelik korunur
    finally:
        app.dependency_overrides.clear()


def test_delete_account_olmayan_404(db_session):
    """accounts.py:222-223 — olmayan hesap 404."""
    try:
        assert _client(db_session).delete("/api/accounts/99999").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_delete_emanet_403(db_session):
    """accounts.py:225-229 — emanet hesap silinemez (MC1)."""
    try:
        emanet = Account(user_id=1, name="Emanet Altin", account_type=AccountType.investment,
                         balance=1000, is_emanet=True)
        db_session.add(emanet); db_session.commit(); db_session.refresh(emanet)
        r = _client(db_session).delete(f"/api/accounts/{emanet.id}")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_delete_bagimli_transaction_409(db_session):
    """accounts.py:234-243 — bağlı işlem varken silme 409."""
    try:
        acc = _cash(db_session)
        db_session.add(Transaction(user_id=1, account_id=acc.id,
                                   transaction_type=TransactionType.expense, amount=100,
                                   category="market", transaction_date=date.today()))
        db_session.commit()
        r = _client(db_session).delete(f"/api/accounts/{acc.id}")
        assert r.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_delete_basarili_204(db_session):
    """accounts.py:245-247 — bağımsız hesap başarılı silinir (204)."""
    try:
        acc = _cash(db_session)
        r = _client(db_session).delete(f"/api/accounts/{acc.id}")
        assert r.status_code == 204
        assert db_session.get(Account, acc.id) is None
    finally:
        app.dependency_overrides.clear()
