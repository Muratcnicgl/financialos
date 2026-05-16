"""
Debt Strategy Engine unit testleri — Snowball + Avalanche.
100% deterministik, LLM yok. conftest.py db_session + test_user fixture kullanilir.
Account kayitlari flush()'lanir, commit edilmez -> rollback ile temizlenir.
"""
from __future__ import annotations

import pytest

from app.debt_strategy import (
    MAX_MONTHS,
    DebtItem,
    calc_avalanche,
    calc_snowball,
    collect_debts,
    compare_strategies,
)
from app.models import Account, AccountType


# ============================================================
# YARDIMCI FACTORY
# ============================================================

def _loan(db, user_id, balance, monthly_payment, interest_rate=0.0,
          remaining=None, name="Test Kredi"):
    a = Account(
        user_id=user_id, name=name,
        account_type=AccountType.loan,
        balance=balance,
        monthly_payment=monthly_payment,
        interest_rate=interest_rate,
        remaining_installments=remaining,
    )
    db.add(a)
    db.flush()
    return a


def _card(db, user_id, balance, credit_limit=20000, interest_rate=None,
          name="Test Kart"):
    a = Account(
        user_id=user_id, name=name,
        account_type=AccountType.credit_card,
        balance=balance,
        credit_limit=credit_limit,
        interest_rate=interest_rate,  # None -> DEFAULT_CARD_INTEREST_MONTHLY
    )
    db.add(a)
    db.flush()
    return a


# ============================================================
# TEST 1 — Bos veri
# ============================================================

def test_empty_no_debts(db_session, test_user):
    """Hic borc hesabi yoksa compare_strategies bos donmeli."""
    result = compare_strategies(db_session, test_user.id)

    assert result['debts'] == []
    assert result['snowball'] is None
    assert result['avalanche'] is None
    assert 'Aktif borc yok' in result['comparison']['recommendation_note']


# ============================================================
# TEST 2 — Tek kredili, faizsiz
# ============================================================

def test_single_loan_no_interest(db_session, test_user):
    """1000 TL, faizsiz, 100 TL/ay -> tam 10 ayda bitmeli, faiz=0."""
    _loan(db_session, test_user.id,
          balance=1000.0, monthly_payment=100.0,
          interest_rate=0.0, remaining=10)

    debts = collect_debts(db_session, test_user.id)
    assert len(debts) == 1

    result = calc_avalanche(debts, extra_monthly=0.0)
    assert result.months_to_freedom == 10
    assert result.total_interest_paid == 0.0
    assert debts[0].account_id in result.debt_payoff_months
    assert result.debt_payoff_months[debts[0].account_id] == 10


# ============================================================
# TEST 3 — Iki kredi: avalanche yuksek faizi once odemeliydi
# ============================================================

def test_two_loans_avalanche_picks_higher_rate(db_session, test_user):
    """
    Yuksek bakiyeli / yuksek faizli kredi ile kucuk bakiyeli / dusuk faizli:
    - Avalanche: yuksek faiz (A) once
    - Snowball:  kucuk bakiye (B) once
    Avalanche => toplam faiz <= snowball toplam faiz
    """
    a = _loan(db_session, test_user.id,
              balance=10000.0, monthly_payment=500.0,
              interest_rate=5.0, name="Yuksek Faiz (A)")
    b = _loan(db_session, test_user.id,
              balance=5000.0, monthly_payment=500.0,
              interest_rate=2.0, name="Dusuk Bakiye (B)")

    debts = collect_debts(db_session, test_user.id)
    assert len(debts) == 2

    snowball = calc_snowball(debts)
    avalanche = calc_avalanche(debts)

    # Avalanche yuksek faizliye (A) once odeme yapar
    assert avalanche.order[0] == a.id

    # Snowball kucuk bakiyeye (B) once odeme yapar
    assert snowball.order[0] == b.id

    # Avalanche genelde daha az faiz odemeli (ya da esit)
    assert avalanche.total_interest_paid <= snowball.total_interest_paid


# ============================================================
# TEST 4 — Murat'in gercek senaryosu
# ============================================================

def test_murat_real_scenario(db_session, test_user):
    """
    Gercek veri: Ziraat Kart (11823, %4.25 default), Garanti 1 (32879, %4.75),
    Garanti 2 (30761, %4.55). Extra=0.
    """
    ziraat = _card(db_session, test_user.id,
                   balance=11822.66, credit_limit=12000,
                   interest_rate=None, name="Ziraat Kredi Karti")
    garanti1 = _loan(db_session, test_user.id,
                     balance=32879.25, monthly_payment=4109.9,
                     interest_rate=4.75, remaining=8, name="Garanti Kredi 1")
    garanti2 = _loan(db_session, test_user.id,
                     balance=30760.61, monthly_payment=4394.36,
                     interest_rate=4.55, remaining=7, name="Garanti Kredi 2")

    debts = collect_debts(db_session, test_user.id)
    assert len(debts) == 3

    snowball = calc_snowball(debts)
    avalanche = calc_avalanche(debts)

    # Snowball: bakiye kucukten buyuge
    # Ziraat Kart (11823) -> Garanti 2 (30761) -> Garanti 1 (32879)
    assert snowball.order[0] == ziraat.id

    # Avalanche: faiz yuksekten dusuge
    # Garanti 1 (4.75%) -> Garanti 2 (4.55%) -> Ziraat Kart (4.25% default)
    assert avalanche.order[0] == garanti1.id

    # Her iki strateji de bitiyor (cok uzun surse de)
    assert 0 < snowball.months_to_freedom <= MAX_MONTHS
    assert 0 < avalanche.months_to_freedom <= MAX_MONTHS

    # Tum 3 borc her iki stratejide de bitmeli
    for aid in [ziraat.id, garanti1.id, garanti2.id]:
        assert aid in snowball.debt_payoff_months, f"Snowball: {aid} bitmedi"
        assert aid in avalanche.debt_payoff_months, f"Avalanche: {aid} bitmedi"


# ============================================================
# TEST 5 — Ekstra odeme hizlandirma
# ============================================================

def test_extra_payment_speeds_up(db_session, test_user):
    """Extra=500 TL ile hem daha az faiz hem daha hizli bitiyor."""
    _loan(db_session, test_user.id,
          balance=5000.0, monthly_payment=200.0,
          interest_rate=3.0, name="Kredi A")
    _loan(db_session, test_user.id,
          balance=8000.0, monthly_payment=300.0,
          interest_rate=2.0, name="Kredi B")

    debts = collect_debts(db_session, test_user.id)

    no_extra  = calc_avalanche(debts, extra_monthly=0.0)
    with_extra = calc_avalanche(debts, extra_monthly=500.0)

    assert with_extra.total_interest_paid < no_extra.total_interest_paid
    assert with_extra.months_to_freedom < no_extra.months_to_freedom


# ============================================================
# TEST 6 — MAX_MONTHS koruma
# ============================================================

def test_max_months_limit(db_session, test_user):
    """
    Faiz > odeme: bakiye buyur, hic bitmez.
    months_to_freedom == MAX_MONTHS olmali (sonsuz dongu yok).
    """
    # 100 TL/ay odeme vs 10% aylik faiz → 10.000 TL/ay faiz — asla bitmez
    _loan(db_session, test_user.id,
          balance=100_000.0, monthly_payment=100.0,
          interest_rate=10.0, name="Imkansiz Kredi")

    debts = collect_debts(db_session, test_user.id)
    result = calc_avalanche(debts, extra_monthly=0.0)

    assert result.months_to_freedom == MAX_MONTHS
