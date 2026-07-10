"""
Per-file denetim (ajan taraması) bulgularının düzeltme testleri — BUG #086, #089, #090.
Kök vizyon: "çift sayma yasak" + "sıfır matematik hatası".

Deterministik: DB gerektirenler izole in-memory (conftest db_session); saf olanlar model/dataclass.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models import RecurringIncome, Transaction, GoalRule, TransactionType
from app.rules_engine import _calculate_expected_income_until_eom
from app.goal_rules import _compute_allocation_amount
from app.debt_strategy import DebtItem, calc_avalanche


# ============================================================
# BUG #086 — beklenen gelir çift-sayımı (kurucu "çift sayma yasak")
# ============================================================

def test_086_bu_ay_tetiklenen_gelir_beklenene_sayilmaz(db_session, test_user):
    """last_triggered_year_month == bu ay olan gelir (nakde geçmiş) beklenen'e SAYILMAZ."""
    today = date(2026, 5, 15)
    ym = "2026-05"
    # Zaten bu ay tetiklenmiş (nakde geçmiş) — beklenen'e sayılmamalı
    db_session.add(RecurringIncome(
        user_id=test_user.id, name="Maaş", amount=50000.0, day_of_month=10,
        is_active=True, last_triggered_year_month=ym,
    ))
    # Henüz tetiklenmemiş, ayın 20'sinde gelecek — beklenen'e sayılmalı
    db_session.add(RecurringIncome(
        user_id=test_user.id, name="Kira geliri", amount=8000.0, day_of_month=20,
        is_active=True, last_triggered_year_month=None,
    ))
    db_session.commit()

    total, upcoming = _calculate_expected_income_until_eom(test_user.id, today, db_session)

    assert total == 8000.0, f"Tetiklenmiş maaş çift sayıldı: {total}"
    assert len(upcoming) == 1
    assert upcoming[0]["ad"] == "Kira geliri"


def test_086_tetiklenmemis_gelir_normal_sayilir(db_session, test_user):
    """Kontrol: hiç tetiklenmemiş gelir eskisi gibi beklenen'e sayılır."""
    today = date(2026, 5, 1)
    db_session.add(RecurringIncome(
        user_id=test_user.id, name="Maaş", amount=50000.0, day_of_month=10,
        is_active=True, last_triggered_year_month="2026-04",  # geçen ay tetiklenmiş, bu ay değil
    ))
    db_session.commit()

    total, upcoming = _calculate_expected_income_until_eom(test_user.id, today, db_session)
    assert total == 50000.0
    assert len(upcoming) == 1


# ============================================================
# BUG #090 — goal_rules full/percent/fixed işaret farkındalığı
# ============================================================

def _mk_tx(amount, tx_type):
    return Transaction(amount=amount, transaction_type=tx_type, category="x")


def _mk_rule(alloc_type, alloc_value=None):
    return GoalRule(allocation_type=alloc_type, allocation_value=alloc_value)


def test_090_gider_full_negatif():
    """Gidere eşleşen full kural withdrawal (−) olmalı — progress'i şişirmemeli."""
    amt = _compute_allocation_amount(_mk_tx(5000.0, TransactionType.expense), _mk_rule("full"))
    assert amt == Decimal("-5000")


def test_090_gelir_full_pozitif():
    amt = _compute_allocation_amount(_mk_tx(5000.0, TransactionType.income), _mk_rule("full"))
    assert amt == Decimal("5000")


def test_090_transfer_full_pozitif():
    """Transfer contribution (+) sayılır (test_09 ile tutarlı)."""
    amt = _compute_allocation_amount(_mk_tx(1500.0, TransactionType.transfer), _mk_rule("full"))
    assert amt == Decimal("1500")


def test_090_gider_percent_negatif():
    amt = _compute_allocation_amount(
        _mk_tx(10000.0, TransactionType.expense), _mk_rule("percent", Decimal("30")))
    assert amt == Decimal("-3000.00")


def test_090_gider_fixed_negatif():
    amt = _compute_allocation_amount(
        _mk_tx(9999.0, TransactionType.expense), _mk_rule("fixed", Decimal("500")))
    assert amt == Decimal("-500")


def test_090_gelir_fixed_pozitif():
    amt = _compute_allocation_amount(
        _mk_tx(9999.0, TransactionType.income), _mk_rule("fixed", Decimal("500")))
    assert amt == Decimal("500")


# ============================================================
# BUG #089 — kart rollover stale başlangıç minimumu (iyimser payoff)
# ============================================================

def test_089_kart_rollover_stale_min_kullanmaz():
    """
    Kart bitince rollover'a FİİLEN ödenen (azalmış) minimum eklenmeli, stale büyük
    başlangıç min_payment DEĞİL. Aksi halde kredi hayalet parayla çok hızlı kapanır.
    """
    # Kart: küçük bakiye (2 ayda kapanır), stale/yanlış büyük min_payment=999 veriyoruz.
    # _simulate kart minimumunu her ay bakiyeden yeniden hesaplar (max(bal*0.25, 50)),
    # yani gerçek aylık ödeme ~50; rollover'a 999 DEĞİL ~50 eklenmeli.
    card = DebtItem(account_id=1, name="Kart", account_type="credit_card",
                    balance=100.0, interest_rate_monthly=0.0, min_payment=999.0)
    loan = DebtItem(account_id=2, name="Kredi", account_type="loan",
                    balance=10000.0, interest_rate_monthly=0.0, min_payment=100.0)

    res = calc_avalanche([card, loan], extra_monthly=0.0)

    # Faizsiz: toplam ödenen = toplam anapara (korunma)
    assert abs(res.total_paid - 10100.0) < 1.0
    # Stale 999 rollover olsaydı kredi ~11 ayda biterdi; fiilen ödenen ~50 rollover ile
    # çok daha uzun sürer. 30+ ay = stale min kullanılMADIĞInın kanıtı.
    assert res.months_to_freedom > 30, (
        f"Kredi çok hızlı kapandı (months={res.months_to_freedom}) — stale kart min'i "
        f"rollover'a sızmış olabilir (BUG #089 regresyonu)."
    )
