"""
Property-based invariant testleri — yeni metriklerin HER girdide sağlaması gereken sınırlar.
Manuel gözlemle doğruladığım robustluğu (adversarial edge sweep) rastgele girdilerle kilitler.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from hypothesis import given, strategies as st, settings

from app.rules_engine import calculate_health_score, _calculate_safe_to_spend
from app.goal_engine import sinking_fund_plan

_floats = st.floats(min_value=-1e7, max_value=1e7, allow_nan=False, allow_infinity=False)
_pos = st.floats(min_value=0, max_value=1e7, allow_nan=False, allow_infinity=False)


@given(
    reel_butce=_floats, kart_borcu=_pos, kart_limit=_pos, aylik_faiz=_pos,
    aylik_gelir=_pos, runway_gun=st.one_of(st.none(), st.integers(min_value=0, max_value=100000)),
    crunch_var=st.booleans(), zarf_asan=st.integers(min_value=0, max_value=20),
    zarf_var=st.booleans(),
)
@settings(max_examples=200)
def test_health_score_daima_0_100(reel_butce, kart_borcu, kart_limit, aylik_faiz,
                                  aylik_gelir, runway_gun, crunch_var, zarf_asan, zarf_var):
    r = calculate_health_score(
        reel_butce=reel_butce, kart_borcu=kart_borcu, kart_limit=kart_limit,
        aylik_faiz=aylik_faiz, aylik_gelir=aylik_gelir, runway_gun=runway_gun,
        crunch_var=crunch_var, zarf_asan=zarf_asan, zarf_var=zarf_var,
    )
    assert 0 <= r["skor"] <= 100
    assert r["seviye"] in ("iyi", "orta", "kritik")
    for b in r["bilesenler"]:
        assert 0 <= b["puan"] <= 100          # her bileşen de sınırlı


@given(lowest=_floats, kart_borcu=_pos, buffer=_pos)
@settings(max_examples=200)
def test_safe_to_spend_daima_negatif_degil(lowest, kart_borcu, buffer):
    r = _calculate_safe_to_spend({"lowest_balance": lowest}, kart_borcu=kart_borcu, buffer=buffer)
    assert r >= 0.0
    assert r <= max(0.0, lowest) + 0.01       # kart/buffer düşülünce lowest'ı aşmaz (kuruş yuvarlama toleransı)


@given(
    target=st.floats(min_value=0.01, max_value=1e6, allow_nan=False),
    current=st.floats(min_value=0, max_value=1e6, allow_nan=False),
    months_ahead=st.integers(min_value=-6, max_value=36),
)
@settings(max_examples=200)
def test_sinking_fund_aylik_gereken_negatif_degil(target, current, months_ahead):
    from app.debt_strategy import _add_months
    today = date(2026, 1, 15)
    target_date = _add_months(today, months_ahead) if months_ahead >= 0 else _add_months(today, months_ahead)
    r = sinking_fund_plan(Decimal(str(round(target, 2))), target_date, Decimal(str(round(current, 2))), today=today)
    assert r is not None
    assert r["aylik_gereken"] >= 0
    assert r["kalan_ay"] >= 0


# ============================================================
# UÇTAN-UCA FİNİTLİK — SONLU girdide generate_cockpit ASLA inf/NaN üretmez.
# SEC-032 finiteness garantilerinin TÜM cockpit hesabı boyunca korunduğunu kilitler
# (round(inf)/taşma sınıfı bir daha sessizce dönemez).
# ============================================================
import math  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from app.models import (Base, User, Account, AccountType, Transaction,  # noqa: E402
                        TransactionType, PersonalDebt, DebtDirection, RecurringIncome)
from app.rules_engine import generate_cockpit  # noqa: E402

_COCKPIT_TODAY = date(2026, 7, 12)
_fin = st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False)
_rate = st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)


def _assert_all_finite(obj, path="root"):
    if isinstance(obj, float):
        assert math.isfinite(obj), f"non-finite float at {path}: {obj}"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_all_finite(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_all_finite(v, f"{path}[{i}]")


@st.composite
def _portfoy(draw):
    accs = [("cash", draw(_fin), None, None, None, None)]
    if draw(st.booleans()):
        accs.append(("credit_card", draw(_fin), draw(st.floats(1, 1e6, allow_nan=False, allow_infinity=False)),
                     draw(st.integers(1, 28)), draw(st.integers(1, 28)), draw(_rate)))
    for _ in range(draw(st.integers(0, 2))):
        accs.append(("loan", draw(_fin), None, None, None, draw(_rate)))
    return accs


@given(portfoy=_portfoy(), n_txn=st.integers(0, 5), n_debt=st.integers(0, 3))
@settings(max_examples=40, deadline=None)
def test_generate_cockpit_daima_finite(portfoy, n_txn, n_debt):
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    try:
        s.add(User(id=1, name="m"))
        for i, (atype, bal, lim, sd, pd_, rate) in enumerate(portfoy):
            s.add(Account(user_id=1, name=f"a{i}", account_type=AccountType(atype), balance=bal,
                          credit_limit=lim, statement_day=sd, payment_day=pd_, interest_rate=rate,
                          monthly_payment=(bal * 0.05 if atype == "loan" else None),
                          remaining_installments=(12 if atype == "loan" else None)))
        for j in range(n_txn):
            s.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=50.0 + j,
                              category="market", transaction_date=_COCKPIT_TODAY))
        for k in range(n_debt):
            s.add(PersonalDebt(user_id=1, counterparty=f"K{k}", direction=DebtDirection.receivable,
                               amount=1000.0 + k, is_paid=False))
        s.add(RecurringIncome(user_id=1, name="Maas", amount=25000, day_of_month=15, is_active=True))
        s.commit()
        cockpit = generate_cockpit(1, _COCKPIT_TODAY, s)   # ASLA exception
        cockpit.pop("_coach_extra_numbers", None)          # iç ayrıntı
        _assert_all_finite(cockpit)
    finally:
        s.close()
