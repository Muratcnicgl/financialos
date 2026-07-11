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
