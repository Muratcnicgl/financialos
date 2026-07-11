"""
RULE-010 fix: debt payoff_date artık GERÇEK takvim ayı (today + month*30 gün DEĞİL) +
`today` enjekte edilebilir (deterministik). Bu, FEAT-012 borçsuzluk tarihinin doğruluğu için önemli.
"""
from __future__ import annotations

from datetime import date

from app.debt_strategy import DebtItem, calc_avalanche, _add_months


def test_add_months_takvim():
    assert _add_months(date(2026, 1, 15), 12) == date(2027, 1, 15)      # tam yıl
    assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)       # ay sonu clamp
    assert _add_months(date(2026, 11, 10), 3) == date(2027, 2, 10)      # yıl aşımı
    # 30-gün yaklaşımıyla FARK: 12 ay = 360 gün → 2026-12-31 (yanlış); takvim → 2027-01-15
    assert _add_months(date(2026, 1, 15), 12) != date(2026, 1, 15) + __import__("datetime").timedelta(days=360)


def test_payoff_date_enjekte_edilen_today_ile_deterministik():
    debts = [DebtItem(account_id=1, name="Kredi", account_type="loan",
                      balance=10000.0, interest_rate_monthly=2.0, min_payment=2000.0)]
    r = calc_avalanche(debts, extra_monthly=0.0, today=date(2026, 1, 15))
    # payoff_date = ay-başı + months_to_freedom takvim ayı (gerçek takvim)
    assert r.payoff_date == _add_months(date(2026, 1, 15), r.months_to_freedom)
    assert r.months_to_freedom >= 1
