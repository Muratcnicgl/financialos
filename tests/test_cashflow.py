"""
Cashflow forecast motoru testleri — H2G1.

Her test db_session + test_user fixture'ını kullanır (conftest.py).
Test verisi flush()'lanır, commit edilmez → conftest rollback ile temizlenir.
"""

from datetime import date, timedelta

import pytest

from app.cashflow import generate_forecast, _month_occurrences
from app.models import (
    Account, AccountType,
    PersonalDebt, DebtDirection,
    RecurringIncome, RecurringExpense,
)


# ============================================================
# YARDIMCI FACTORY'LER
# ============================================================

def _cash_account(db, user_id, balance=1000.0, name="Test Nakit"):
    acc = Account(
        user_id=user_id, name=name,
        account_type=AccountType.cash, balance=balance,
    )
    db.add(acc)
    db.flush()
    return acc


def _loan_account(db, user_id, monthly_payment, next_payment_date, name="Test Kredi"):
    acc = Account(
        user_id=user_id, name=name,
        account_type=AccountType.loan, balance=monthly_payment * 3,
        monthly_payment=monthly_payment, next_payment_date=next_payment_date,
    )
    db.add(acc)
    db.flush()
    return acc


def _cash_acc_for_expense(db, user_id):
    """RecurringExpense account_id FK için minimal cash account."""
    return _cash_account(db, user_id, balance=0.0, name="Gider Hesabı")


def _recurring_income(db, user_id, amount, day_of_month, name="Test Gelir"):
    inc = RecurringIncome(
        user_id=user_id, name=name, amount=amount,
        day_of_month=day_of_month, is_active=True,
    )
    db.add(inc)
    db.flush()
    return inc


def _recurring_expense(db, user_id, account_id, amount, day_of_month, name="Test Gider"):
    exp = RecurringExpense(
        user_id=user_id, name=name, amount=amount,
        account_id=account_id, day_of_month=day_of_month, is_active=True,
    )
    db.add(exp)
    db.flush()
    return exp


def _receivable(db, user_id, amount, due_date, counterparty="Test", is_paid=False):
    d = PersonalDebt(
        user_id=user_id, counterparty=counterparty,
        direction=DebtDirection.receivable, amount=amount,
        due_date=due_date, is_paid=is_paid,
    )
    db.add(d)
    db.flush()
    return d


def _payable(db, user_id, amount, due_date, counterparty="Test", is_paid=False):
    d = PersonalDebt(
        user_id=user_id, counterparty=counterparty,
        direction=DebtDirection.payable, amount=amount,
        due_date=due_date, is_paid=is_paid,
    )
    db.add(d)
    db.flush()
    return d


# ============================================================
# TEST 1 — Boş veri: yapı doğru
# ============================================================

def test_empty_data_returns_correct_structure(db_session, test_user):
    """Hiç veri olmasa bile days array horizon_days eleman içerir."""
    result = generate_forecast(db_session, test_user.id, horizon_days=7)

    assert result["horizon_days"] == 7
    assert result["currency"] == "TRY"
    assert len(result["days"]) == 7
    assert result["summary"]["total_receivable"] == 0.0
    assert result["summary"]["total_payable"] == 0.0
    assert result["summary"]["net_flow"] == 0.0
    assert result["sankey"]["nodes"] == []
    assert result["sankey"]["links"] == []


# ============================================================
# TEST 2 — Tek recurring income: doğru genişleme
# ============================================================

def test_single_recurring_income_expands_correctly(db_session, test_user):
    """Recurring income horizon içinde doğru günde giriş olarak görünür."""
    today = date.today()
    _cash_account(db_session, test_user.id, balance=500.0)

    # Yarın gelecek şekilde day_of_month ayarla
    tomorrow = today + timedelta(days=1)
    _recurring_income(db_session, test_user.id, amount=3000.0,
                      day_of_month=tomorrow.day, name="Maaş")

    result = generate_forecast(db_session, test_user.id, horizon_days=30)

    # Yarınki gün inflow içermeli
    tomorrow_day = next(d for d in result["days"] if d.date == tomorrow)
    assert tomorrow_day.inflows == 3000.0
    assert tomorrow_day.closing_balance == 3500.0

    # Olaylar listesinde kayıt var
    assert len(tomorrow_day.events) == 1
    assert tomorrow_day.events[0].source_type == "income"
    assert tomorrow_day.events[0].amount == 3000.0


# ============================================================
# TEST 3 — Tek recurring expense: negatif outflow
# ============================================================

def test_single_recurring_expense_is_negative_outflow(db_session, test_user):
    """Recurring expense outflow negatif olarak işlenir, bakiyeyi düşürür."""
    today = date.today()
    acc = _cash_account(db_session, test_user.id, balance=2000.0)

    tomorrow = today + timedelta(days=1)
    _recurring_expense(db_session, test_user.id, account_id=acc.id,
                       amount=500.0, day_of_month=tomorrow.day, name="Kira")

    result = generate_forecast(db_session, test_user.id, horizon_days=5)

    tomorrow_day = next(d for d in result["days"] if d.date == tomorrow)
    assert tomorrow_day.outflows == -500.0
    assert tomorrow_day.closing_balance == 1500.0
    assert tomorrow_day.events[0].source_type == "recurring_expense"
    assert tomorrow_day.events[0].amount == -500.0


# ============================================================
# TEST 4 — PersonalDebt receivable yarın: giriş olarak görünür
# ============================================================

def test_receivable_due_tomorrow_appears_as_inflow(db_session, test_user):
    """Yarın vadesi gelen ödenmemiş alacak, inflow olarak görünür."""
    today = date.today()
    _cash_account(db_session, test_user.id, balance=0.0)
    tomorrow = today + timedelta(days=1)
    _receivable(db_session, test_user.id, amount=750.0,
                due_date=tomorrow, counterparty="Efe")

    result = generate_forecast(db_session, test_user.id, horizon_days=5)

    tomorrow_day = next(d for d in result["days"] if d.date == tomorrow)
    assert tomorrow_day.inflows == 750.0
    assert len(tomorrow_day.events) == 1
    assert tomorrow_day.events[0].source_type == "receivable"
    assert "Efe" in tomorrow_day.events[0].label


# ============================================================
# TEST 5 — Ödenmiş alacak: dahil edilmez
# ============================================================

def test_paid_receivable_is_excluded(db_session, test_user):
    """is_paid=True olan alacak forecast'e dahil edilmez."""
    today = date.today()
    _cash_account(db_session, test_user.id, balance=0.0)
    tomorrow = today + timedelta(days=1)
    _receivable(db_session, test_user.id, amount=750.0,
                due_date=tomorrow, counterparty="Efe", is_paid=True)

    result = generate_forecast(db_session, test_user.id, horizon_days=5)

    total_inflow = sum(d.inflows for d in result["days"])
    assert total_inflow == 0.0
    assert result["summary"]["total_receivable"] == 0.0


# ============================================================
# TEST 6 — Crunch tespiti
# ============================================================

def test_crunch_detection_marks_correct_days(db_session, test_user):
    """Bakiye crunch_threshold altına düştüğünde day.crunch=True olur."""
    today = date.today()
    _cash_account(db_session, test_user.id, balance=200.0)
    acc = _cash_acc_for_expense(db_session, test_user.id)

    # 3 gün sonra büyük bir gider — bakiyeyi 200 → -300'e çeker
    target_day = today + timedelta(days=3)
    _recurring_expense(db_session, test_user.id, account_id=acc.id,
                       amount=500.0, day_of_month=target_day.day, name="Büyük Gider")

    result = generate_forecast(
        db_session, test_user.id, horizon_days=10, crunch_threshold=0.0
    )

    # Giderden önce crunch yok
    before_day = next(d for d in result["days"] if d.date == today + timedelta(days=2))
    assert not before_day.crunch

    # Gider günü ve sonrası crunch
    crunch_day = next(d for d in result["days"] if d.date == target_day)
    assert crunch_day.crunch
    assert result["summary"]["crunch_count"] > 0
    assert target_day.isoformat() in result["summary"]["crunch_dates"]


# ============================================================
# TEST 7 — Filtre chip: sadece incomes
# ============================================================

def test_include_filter_incomes_only_excludes_expenses(db_session, test_user):
    """include='incomes' ile yalnızca gelirler dahil edilir, giderler hariç."""
    today = date.today()
    acc = _cash_account(db_session, test_user.id, balance=1000.0)

    tomorrow = today + timedelta(days=1)
    _recurring_income(db_session, test_user.id, amount=2000.0,
                      day_of_month=tomorrow.day, name="Maaş")
    _recurring_expense(db_session, test_user.id, account_id=acc.id,
                       amount=300.0, day_of_month=tomorrow.day, name="Abonelik")
    _receivable(db_session, test_user.id, amount=500.0,
                due_date=tomorrow, counterparty="Ali")

    result = generate_forecast(
        db_session, test_user.id, horizon_days=5,
        include={"incomes"},
    )

    total_outflow = sum(d.outflows for d in result["days"])
    assert total_outflow == 0.0
    assert result["summary"]["total_payable"] == 0.0

    total_inflow = sum(d.inflows for d in result["days"])
    assert total_inflow == 2000.0  # sadece income, alacak hariç


# ============================================================
# TEST 8 — Sankey: 1 gelir + 2 gider kaynağı → doğru node/link
# ============================================================

def test_sankey_builds_correct_nodes_and_links(db_session, test_user):
    """1 gelir + 2 farklı gider → Sankey'de doğru node ve link sayısı."""
    today = date.today()
    acc = _cash_account(db_session, test_user.id, balance=5000.0)

    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    _recurring_income(db_session, test_user.id, amount=3000.0,
                      day_of_month=tomorrow.day, name="Maaş")
    _recurring_expense(db_session, test_user.id, account_id=acc.id,
                       amount=800.0, day_of_month=day_after.day, name="Kira")
    _recurring_expense(db_session, test_user.id, account_id=acc.id,
                       amount=200.0, day_of_month=day_after.day, name="Netflix")

    result = generate_forecast(db_session, test_user.id, horizon_days=10)

    nodes = result["sankey"]["nodes"]
    links = result["sankey"]["links"]

    node_names = {n["name"] for n in nodes}
    assert "Nakit" in node_names
    assert "Maaş" in node_names
    assert "Kira" in node_names
    assert "Netflix" in node_names
    assert len(nodes) == 4  # Nakit + 1 gelir + 2 gider

    # Link sayısı: Maaş→Nakit + Nakit→Kira + Nakit→Netflix = 3
    assert len(links) == 3

    # Gelir linki Nakit'e gider
    cash_idx = next(n["id"] for n in nodes if n["name"] == "Nakit")
    maas_link = next(lnk for lnk in links if lnk["label"] == "Maaş")
    assert maas_link["target"] == cash_idx
    assert maas_link["value"] == 3000.0


# ============================================================
# TEST 9 — Horizon sınırı: son gün dahil, sonrası hariç
# ============================================================

def test_horizon_boundary_last_day_included(db_session, test_user):
    """horizon_days'in son günündeki olay dahil, sonraki gün hariç."""
    today = date.today()
    _cash_account(db_session, test_user.id, balance=0.0)

    last_day = today + timedelta(days=4)   # 5 günlük tahmin, index 4
    after_horizon = today + timedelta(days=5)

    _receivable(db_session, test_user.id, amount=100.0,
                due_date=last_day, counterparty="Son Gün")
    _receivable(db_session, test_user.id, amount=200.0,
                due_date=after_horizon, counterparty="Dışarıda")

    result = generate_forecast(db_session, test_user.id, horizon_days=5)

    assert len(result["days"]) == 5
    last = result["days"][-1]
    assert last.date == last_day

    # Sadece 100 TL dahil, 200 TL değil
    assert result["summary"]["total_receivable"] == 100.0


# ============================================================
# TEST 10 — Determinizm: aynı girdi aynı çıktı
# ============================================================

def test_determinism_same_input_same_output(db_session, test_user):
    """Aynı veriyle iki kez çağrıldığında özdeş özet döner."""
    today = date.today()
    _cash_account(db_session, test_user.id, balance=1500.0)
    acc = _cash_acc_for_expense(db_session, test_user.id)

    next_day = today + timedelta(days=1)
    _recurring_income(db_session, test_user.id, amount=2500.0,
                      day_of_month=next_day.day, name="Gelir")
    _recurring_expense(db_session, test_user.id, account_id=acc.id,
                       amount=400.0, day_of_month=next_day.day, name="Gider")

    r1 = generate_forecast(db_session, test_user.id, horizon_days=14)
    r2 = generate_forecast(db_session, test_user.id, horizon_days=14)

    assert r1["summary"] == r2["summary"]
    assert r1["start_date"] == r2["start_date"]
    assert r1["end_date"] == r2["end_date"]
    assert len(r1["days"]) == len(r2["days"])
    for d1, d2 in zip(r1["days"], r2["days"]):
        assert d1.closing_balance == d2.closing_balance


# ============================================================
# TEST 11 — _month_occurrences yardımcısı
# ============================================================

def test_month_occurrences_crosses_month_boundary():
    """_month_occurrences birden fazla ay boyunca doğru genişler."""
    start = date(2026, 5, 20)
    end = date(2026, 7, 5)
    results = _month_occurrences(start, end, day_of_month=15)
    # 15 Mayıs < start, 15 Haziran, 15 Temmuz < end
    assert date(2026, 6, 15) in results
    assert date(2026, 7, 15) not in results  # 15 Temmuz > 5 Temmuz
    assert date(2026, 5, 15) not in results  # < start


def test_month_occurrences_day_clamped_to_month_end():
    """31'in olmadığı ayda son güne kenetlenir."""
    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    results = _month_occurrences(start, end, day_of_month=31)
    assert results == [date(2026, 2, 28)]
