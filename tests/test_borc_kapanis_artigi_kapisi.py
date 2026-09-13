"""
RULE-012 / BUG #438 KAPISI — BORÇ KAPANIŞ ARTIĞI SON ÖDEMEYE EKLENİR; KORUNUM KURUŞ-ALTINDA.

Ölçülen (13 Eyl 2026): `_simulate` ödeme sonrası bakiye < 0,01 kalınca borcu kapatıyor, artığı
`total_paid`'e EKLEMİYOR ve adım 2'de aynı artığı "iade" diye ekstraya EKLİYORDU (yön yanlış).
Rastgele 752 biten senaryoda korunum sapması ≤ 3e-11 (artık yalnız ödeme bakiyenin 1 kuruş
altına düştüğünde oluşur — nadir), yani "korunum bozuk" iddiası PRATİKTE yanlıştı; RULE-031'in
1 TL toleransı ise kusuru hiç ölçmüyordu. Düzeltme: artık son ödemeye eklenir.

Kilitlenen: kurgulu artık senaryosunda son taksit artığı taşır (333,34; eskiden 333,33);
biten senaryolarda korunum 1 kuruş içinde (tohumlu rastgele küme); bitmeyenlerde
kalan bakiye dahil korunum (float büyüklüğüne göre) tutar.
"""
from __future__ import annotations

import random

from app.debt_strategy import MAX_MONTHS, DebtItem, calc_avalanche, calc_snowball


def _debt(aid, balance, rate, minp, atype="loan"):
    return DebtItem(account_id=aid, name=f"d{aid}", account_type=atype, balance=balance,
                    interest_rate_monthly=rate, min_payment=minp)


def test_artik_son_odemeye_eklenir():
    # 1000,004 / 333,333 → 3. taksitten sonra 0,005 artık kalırdı; artık 3. taksite eklenir.
    r = calc_snowball([_debt(1, 1000.004, 0.0, 333.333)], extra_monthly=0)
    assert r.months_to_freedom == 3
    assert r.schedule[-1].paid_this_month[1] == 333.34, r.schedule[-1].paid_this_month
    assert r.schedule[-1].debt_balances[1] == 0.0
    assert abs(r.total_paid - 1000.0) < 0.006


def test_biten_senaryolarda_korunum_bir_kurus_icinde():
    rnd = random.Random(7)  # noqa: S311 — kriptografik değil, tohumlu test kümesi
    biten = 0
    for _ in range(200):
        debts = [_debt(i + 1, round(rnd.uniform(500, 50000), 2), round(rnd.uniform(0, 5), 2),
                       round(rnd.uniform(100, 3000), 2), atype=rnd.choice(["loan", "credit_card"]))
                 for i in range(rnd.randint(1, 4))]
        anapara = sum(d.balance for d in debts)
        for strat in (calc_snowball, calc_avalanche):
            r = strat(debts, extra_monthly=rnd.choice([0, 500, 2000]))
            if r.months_to_freedom >= MAX_MONTHS:
                continue
            biten += 1
            assert abs(r.total_paid - (anapara + r.total_interest_paid)) < 0.01, r.strategy
    assert biten >= 100, "kapsam tabanı (L45): biten senaryo çok az"


def test_bitmeyen_senaryoda_kalan_dahil_korunum():
    """Faiz > asgari: borç asla bitmez; korunum kalan bakiyeyi de sayar (float büyüklüğü kadar tolerans)."""
    debts = [_debt(1, 20000.0, 5.0, 100.0)]
    r = calc_avalanche(debts, extra_monthly=0)
    assert r.months_to_freedom >= MAX_MONTHS
    kalan = r.schedule[-1].debt_balances[1]
    assert abs(r.total_paid - (20000.0 + r.total_interest_paid - kalan)) < max(1.0, kalan * 1e-12)
