"""
Property/invariant testleri — FEAT-014/015/027 borç & alacak metriklerinin HER girdide
sağlaması gereken sınırlar. Manuel gözlemle doğruladığım tutarlılığı rastgele girdilerle
kilitler (round(inf) sağlık-skoru bug'ını yakalayan yöntemin aynısı — _annuity_payment
overflow'u bu turda böyle yakalandı).
"""
from __future__ import annotations

from datetime import date

from hypothesis import given, strategies as st, settings

from app.debt_strategy import (
    DebtItem, _annuity_payment, calculate_consolidation_baseline,
    simulate_consolidation, calculate_min_payment_trap,
)

_bal = st.floats(min_value=1.0, max_value=5e6, allow_nan=False, allow_infinity=False)
_rate = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
TODAY = date(2026, 7, 12)


# ---- _annuity_payment: overflow-safe + faiz ≥ 0 ----------------------------

@given(principal=_bal, rate=_rate, term=st.integers(min_value=1, max_value=3000))
@settings(max_examples=300)
def test_annuity_overflow_safe_ve_faiz_negatif_degil(principal, rate, term):
    p = _annuity_payment(principal, rate, term)   # ASLA OverflowError (guard)
    assert p >= 0
    # toplam ödeme anaparadan az olamaz (faiz ≥ 0) — küçük yuvarlama toleransı
    assert p * term >= principal - 1e-3


# ---- consolidation baseline: ağırlıklı ort. oran min/max arasında ----------

@given(
    debts=st.lists(
        st.tuples(_bal, _rate), min_size=2, max_size=8,
    )
)
@settings(max_examples=200)
def test_konsolidasyon_agirlikli_ort_min_max_arasinda(debts):
    items = [DebtItem(i, f"d{i}", "loan", bal, rate, 0) for i, (bal, rate) in enumerate(debts)]
    b = calculate_consolidation_baseline(items)
    assert b is not None
    assert b["en_dusuk_oran"] - 1e-6 <= b["agirlikli_ort_oran"] <= b["en_yuksek_oran"] + 1e-6
    assert b["toplam_bakiye"] > 0


# ---- simulate_consolidation: oran_avantajli eşikle tutarlı -----------------

@given(
    debts=st.lists(st.tuples(_bal, _rate), min_size=2, max_size=6),
    new_rate=_rate,
    term=st.integers(min_value=1, max_value=360),
)
@settings(max_examples=200)
def test_simulate_avantaj_esikle_tutarli(debts, new_rate, term):
    items = [DebtItem(i, f"d{i}", "loan", bal, rate, 0) for i, (bal, rate) in enumerate(debts)]
    r = simulate_consolidation(items, new_rate, term)
    assert r is not None
    # oran_avantajli == (yeni oran < ağırlıklı ortalama eşiği)
    assert r["oran_avantajli"] == (new_rate < r["agirlikli_ort_oran"])
    assert r["yeni_toplam_faiz"] >= -1e-3          # faiz negatif değil
    assert r["yeni_toplam_odeme"] >= r["toplam_bakiye"] - 1e-3


# ---- min-payment trap: korunum (toplam_odeme = bakiye + toplam_faiz) -------

@given(
    balance=_bal,
    rate=st.floats(min_value=0.1, max_value=33.0, allow_nan=False),  # <%33.3 → biter (asla_bitmez değil)
)
@settings(max_examples=150)
def test_min_trap_korunum_ve_biter(balance, rate):
    t = calculate_min_payment_trap(
        [DebtItem(1, "kart", "credit_card", balance, rate, 0)], today=TODAY)
    k = t["kartlar"][0]
    if not k["asla_bitmez"]:
        # ödenen toplam = anapara + toplam faiz (korunum), kuruş toleransı
        assert abs(k["toplam_odeme"] - (k["bakiye"] + k["toplam_faiz"])) < 1.0
        assert k["toplam_faiz"] >= -1e-3
        assert k["ay"] >= 1
