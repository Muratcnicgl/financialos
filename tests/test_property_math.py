"""
Özellik-tabanlı (property-based) finansal matematik testleri — hypothesis.
Örnek-tabanlı testlerin kaçırdığı KENAR DURUMLARI (yuvarlama, uç değerler, sınırlar) binlerce
rastgele girdiyle avlar. Founding "sıfır hata" mandatı: matematik HER girdide değişmez tutmalı.
"""
from __future__ import annotations

from hypothesis import given, strategies as st, settings

from app.rules_engine import (
    apply_shadow_accounting, calculate_daily_limit, simulate_partial_sale,
)
from app.debt_strategy import DebtItem, calc_avalanche, MAX_MONTHS

# Makul finansal aralıklar (NaN/inf yok, negatif yok)
money = st.floats(min_value=0.0, max_value=1e7, allow_nan=False, allow_infinity=False)
pos_money = st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False)


# ============================================================
# apply_shadow_accounting — Gölge Muhasebe formülü
# ============================================================

@given(cash=money, income=money, card=money, loan=money)
def test_shadow_accounting_formul_kesin(cash, income, card, loan):
    r = apply_shadow_accounting(cash, income, card, loan)
    assert r == round(cash + income - card - loan, 2)


@given(cash=money, income=money, card=money, extra=pos_money)
def test_shadow_accounting_kart_borcu_artinca_azalir(cash, income, card, extra):
    """Kart borcu ARTINCA reel bütçe AZALIR (monoton) — Sanal Zenginlik tuzağı önlemi."""
    r1 = apply_shadow_accounting(cash, income, card, 0.0)
    r2 = apply_shadow_accounting(cash, income, card + extra, 0.0)
    assert r2 <= r1


# ============================================================
# calculate_daily_limit — dinamik günlük limit
# ============================================================

@given(butce=st.floats(-1e6, 1e7, allow_nan=False, allow_infinity=False),
       days=st.integers(min_value=-10, max_value=400))
def test_daily_limit_asla_crash_ve_sifir_gun(butce, days):
    r = calculate_daily_limit(butce, days)
    if days <= 0:
        assert r == 0.0
    else:
        assert r == round(butce / days, 2)
        # işaret tutarlı (yuvarlama ±0.0 sınırı hariç): anlamlı büyüklükte sign eşleşir
        if abs(r) >= 0.01:
            assert (r > 0) == (butce > 0)


# ============================================================
# simulate_partial_sale — stopaj/net değişmezleri
# ============================================================

@given(
    lot_count=st.floats(0.01, 10000, allow_nan=False, allow_infinity=False),
    frac=st.floats(0.001, 1.0, allow_nan=False, allow_infinity=False),
    cost=pos_money, price=pos_money,
)
@settings(max_examples=300)
def test_partial_sale_stopaj_degismezleri(lot_count, frac, cost, price):
    lots = round(lot_count * frac, 4)
    if lots <= 0 or lots > lot_count:
        return  # geçersiz kombinasyon, atla
    sim = simulate_partial_sale(lot_count, cost, price, lots)
    # 1) stopaj hiç negatif olmaz
    assert sim["stopaj"] >= 0
    # 2) zarar/nötr durumda stopaj YOK
    if sim["brut_kar"] <= 0:
        assert sim["stopaj"] == 0.0
    # 3) eline geçen = satış - stopaj (kesin)
    assert sim["net_eline_gecen"] == round(sim["satis_tutari"] - sim["stopaj"], 2)
    # 4) eline geçen satış tutarını AŞAMAZ
    assert sim["net_eline_gecen"] <= sim["satis_tutari"] + 0.01
    # 5) kalan lot doğru
    assert sim["kalan_lot"] == round(lot_count - lots, 4)


# ============================================================
# debt_strategy — PARA KORUNUMU (money conservation)
# ============================================================

debt_item = st.builds(
    DebtItem,
    account_id=st.integers(1, 999),
    name=st.just("borc"),
    account_type=st.sampled_from(["loan", "credit_card"]),
    balance=st.floats(100.0, 200000.0, allow_nan=False, allow_infinity=False),
    interest_rate_monthly=st.floats(0.0, 3.0, allow_nan=False, allow_infinity=False),
    min_payment=st.floats(500.0, 10000.0, allow_nan=False, allow_infinity=False),
)


@given(debts=st.lists(debt_item, min_size=1, max_size=4, unique_by=lambda d: d.account_id))
@settings(max_examples=150, deadline=None)
def test_debt_avalanche_para_korunumu(debts):
    """
    Tüm borçlar kapandıysa: TOPLAM ÖDENEN == başlangıç anaparası + toplam faiz.
    (Para yoktan var/yok olmaz — çift-sayma/kayıp yok.)
    """
    res = calc_avalanche(debts, extra_monthly=0.0)
    if res.months_to_freedom >= MAX_MONTHS:
        return  # kapanmadıysa korunum kısmi; bu senaryoyu atla
    principal = sum(d.balance for d in debts)
    expected = principal + res.total_interest_paid
    # float birikimli yuvarlama toleransı (borç başına ~0.01 * ay)
    assert abs(res.total_paid - expected) <= 1.0 + 0.02 * res.months_to_freedom


# NOT (property-test bulgusu, bug DEĞİL): "avalanche her zaman snowball'dan az faiz öder"
# BU MODELDE EVRENSEL DEĞİL. Karşı-örnek: küçük %0 borç + büyük min_payment (örn. bakiye 501,
# rate 0, min 500). Snowball o küçük borcu ÖNCE kapatıp BÜYÜK minimumu (500) bir ay erken
# serbest bırakır → yüksek-faizli borca daha fazla para akar → daha az faiz. Bu gerçek bir
# kişisel-finans nüansıdır (minimumlar "lumpy" olunca avalanche optimal olmayabilir); kod
# gerçekliği doğru modelliyor ve compare_strategies faizsiz-borç uyarısı veriyor (#081).
# Dolayısıyla bu bir DEĞİŞMEZ olarak ASSERT EDİLMEZ — yanlış-pozitif olurdu.
