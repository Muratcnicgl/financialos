"""
Cashflow forecast motoru testleri — H2G1.

Her test db_session + test_user fixture'ını kullanır (conftest.py).
Test verisi flush()'lanır, commit edilmez → conftest rollback ile temizlenir.
"""

from datetime import date, timedelta

import pytest

from app.cashflow import generate_forecast, _month_occurrences, _expand_loan_payments
from app.models import (
    Account, AccountType,
    PersonalDebt, DebtDirection,
    RecurringIncome, RecurringExpense,
)


# ============================================================
# LOAN FACTORY
# ============================================================

def _loan_account(db, user_id, monthly_payment, next_payment_date,
                  remaining_installments, name="Test Kredi"):
    acc = Account(
        user_id=user_id, name=name,
        account_type=AccountType.loan,
        balance=monthly_payment * remaining_installments,
        monthly_payment=monthly_payment,
        next_payment_date=next_payment_date,
        remaining_installments=remaining_installments,
    )
    db.add(acc)
    db.flush()
    return acc


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


# ============================================================
# BUG #058 — Loan taksit testleri
# ============================================================

def test_loan_payments_included_in_forecast(db_session, test_user):
    """BUG #058: Loan taksitleri 'expenses' chip açıkken forecast'a dahil edilir."""
    today = date.today()
    _cash_account(db_session, test_user.id, balance=20000.0)

    # next_payment_date 5 gün sonra, 2 taksit kalmış
    first_payment = today + timedelta(days=5)
    _loan_account(db_session, test_user.id,
                  monthly_payment=4000.0,
                  next_payment_date=first_payment,
                  remaining_installments=2,
                  name="Test Kredi")

    result = generate_forecast(db_session, test_user.id, horizon_days=60,
                               include={"expenses"})

    # İki taksit: T+5 ve ~T+35 (bir ay sonra)
    total_outflow = abs(result["summary"]["total_payable"])
    assert total_outflow == pytest.approx(8000.0), f"Beklenen 8000 TL, alınan {total_outflow}"
    assert result["summary"]["crunch_count"] == 0  # 20000 - 8000 > 0

    # İlk ödeme günü outflow içermeli
    first_day = next(d for d in result["days"] if d.date == first_payment)
    assert first_day.outflows == pytest.approx(-4000.0)
    event = first_day.events[0]
    assert event.source_type == "loan_payment"
    assert "Test Kredi" in event.label


def test_loan_payments_respect_filter_chip(db_session, test_user):
    """BUG #058: 'incomes' only → loan dahil edilmez; 'expenses' → dahil edilir."""
    today = date.today()
    _cash_account(db_session, test_user.id, balance=5000.0)

    first_payment = today + timedelta(days=3)
    _loan_account(db_session, test_user.id,
                  monthly_payment=2000.0,
                  next_payment_date=first_payment,
                  remaining_installments=3)

    # Sadece incomes filtresi
    r_income_only = generate_forecast(db_session, test_user.id, horizon_days=30,
                                      include={"incomes"})
    assert r_income_only["summary"]["total_payable"] == 0.0

    # expenses filtresi dahil
    r_with_expenses = generate_forecast(db_session, test_user.id, horizon_days=30,
                                        include={"expenses"})
    # 30 gün içinde 1 veya 2 taksit olabilir (3 gün + ~33 gün)
    assert r_with_expenses["summary"]["total_payable"] < 0.0


def test_loan_payments_stop_at_remaining_installments(db_session, test_user):
    """BUG #058: remaining_installments=3 ise horizon=180 günde tam 3 occurrence."""
    today = date.today()
    _cash_account(db_session, test_user.id, balance=50000.0)

    first_payment = today + timedelta(days=2)
    _loan_account(db_session, test_user.id,
                  monthly_payment=1500.0,
                  next_payment_date=first_payment,
                  remaining_installments=3)

    result = generate_forecast(db_session, test_user.id, horizon_days=180,
                               include={"expenses"})

    # Tam 3 loan_payment eventi olmalı
    loan_events = [
        ev
        for day in result["days"]
        for ev in day.events
        if ev.source_type == "loan_payment"
    ]
    assert len(loan_events) == 3, f"Beklenen 3 taksit, alınan {len(loan_events)}"
    assert abs(result["summary"]["total_payable"]) == pytest.approx(4500.0)


def test_rule016_stale_next_payment_date_gelecek_taksitleri_gizlemez():
    """RULE-016: geçmiş (stale) next_payment_date remaining'i boşa harcamamalı — kredi
    forecast'ta tüm KALAN taksitler gelecek yükümlülük olarak görünür (yoksa crunch iyimser)."""
    from app.models import Account, AccountType
    # 6 ay eski next_payment_date + 4 taksit kalan
    acc = Account(id=1, user_id=1, name="Kredi", account_type=AccountType.loan,
                  balance=20000.0, monthly_payment=2500.0, remaining_installments=4,
                  next_payment_date=date(2026, 1, 12))
    start = date(2026, 7, 12)
    ev = _expand_loan_payments(acc, start, start + timedelta(days=180))
    assert len(ev) == 4                       # eskiden 0 (geçmiş occurrence'lar idx'i tüketti)
    assert all(e.date >= start for e in ev)   # hepsi ileriye dönük
    assert ev[0].date == start                # geçmiş-vadeli bugüne çekildi (aya ötelenmedi)


def test_rule016_gelecek_next_payment_date_etkilenmez():
    """Normal (gelecek) next_payment_date davranışı değişmez."""
    from app.models import Account, AccountType
    acc = Account(id=2, user_id=1, name="Kredi2", account_type=AccountType.loan,
                  balance=20000.0, monthly_payment=2500.0, remaining_installments=4,
                  next_payment_date=date(2026, 7, 20))
    start = date(2026, 7, 12)
    ev = _expand_loan_payments(acc, start, start + timedelta(days=180))
    assert len(ev) == 4 and ev[0].date == date(2026, 7, 20)


def test_rule017_ayin_31i_taksiti_surumlenmez():
    """RULE-017: 31'inde taksit Şubat'ta 28'e clamp'lenir ama Mart'ta 31'e DÖNER (sürüklenme yok).
    Eskiden _advance_month current.day'i taşıyıp 28'de kalıyordu."""
    from app.models import Account, AccountType
    acc = Account(id=1, user_id=1, name="Kredi", account_type=AccountType.loan,
                  balance=50000.0, monthly_payment=2000.0, remaining_installments=6,
                  next_payment_date=date(2026, 1, 31))
    ev = _expand_loan_payments(acc, date(2026, 1, 15), date(2026, 5, 15))
    dates = [e.date for e in ev]
    assert date(2026, 2, 28) in dates    # Şubat clamp
    assert date(2026, 3, 31) in dates    # Mart ANCHOR'a döner (sürüklenme yok)
    assert date(2026, 4, 30) in dates


# ============================================================
# PROPERTY / INVARIANT — _expand_loan_payments (RULE-016/017)
# Account transient (session gerekmez) → ucuz fuzzing.
# ============================================================

from hypothesis import given, strategies as st, settings  # noqa: E402

_START = date(2026, 7, 1)


@given(
    off=st.integers(min_value=-400, max_value=400),      # next_payment_date ofseti (stale dahil)
    horizon=st.integers(min_value=1, max_value=400),
    pay=st.floats(min_value=0.0, max_value=1e5, allow_nan=False, allow_infinity=False),
    remaining=st.integers(min_value=0, max_value=60),
)
@settings(max_examples=250, deadline=None)
def test_expand_loan_invariantlari(off, horizon, pay, remaining):
    end = _START + timedelta(days=horizon)
    acc = Account(id=1, name="Kredi", account_type=AccountType.loan,
                  balance=100000.0, monthly_payment=pay,
                  remaining_installments=remaining,
                  next_payment_date=_START + timedelta(days=off))
    events = _expand_loan_payments(acc, _START, end)   # ASLA exception / sonsuz döngü
    # taksit sayısı kalan taksitten fazla olamaz
    assert len(events) <= remaining
    prev = None
    for e in events:
        assert _START <= e.date <= end                 # pencere içinde (stale bile öne çekilir)
        assert e.amount == -pay                          # tutar = -taksit
        assert e.source_type == "loan_payment"
        if prev is not None:
            assert e.date > prev                         # tarihler kesin artan (RULE-017 anchor)
        prev = e.date


def test_expand_loan_rule016_stale_tarih_bosa_gitmez():
    """RULE-016 regresyon: geçmiş (stale) next_payment_date + kalan taksit → occurrence'lar
    KAYBOLMAZ (öne çekilir). Eskiden 0 gelecek ödeme gösterip yükümlülüğü hafife alıyordu."""
    acc = Account(id=1, name="Kredi", account_type=AccountType.loan, balance=50000.0,
                  monthly_payment=2500.0, remaining_installments=4,
                  next_payment_date=_START - timedelta(days=180))  # 6 ay eski
    events = _expand_loan_payments(acc, _START, _START + timedelta(days=150))
    assert len(events) >= 1, "stale tarihli kredi taksitleri forecast'ta görünmeli"
    assert all(e.date >= _START for e in events)
