"""
M83 (Wave-6) — 12 açık RULE maddesinin R3 triyajı sonrası KAPATILAN 5'i test-kilidi.

R3 triyajı (M76 kod-doğrulaması üzerine): 12 AÇIK + 3 KISMEN maddeden gerçek+güvenli-fix
olanlar kapatıldı; kalanlar bilinçli-tasarım / kapsam-ertelenmiş / defekt-değil olarak belgelendi
(bkz. sections/RULE.md M83 notları). Bu dosya kapatılan 5 maddeyi kilitler:
- RULE-025: snowball/avalanche deterministik tie-break (account_id ikincil anahtar)
- RULE-033: percent allocation ROUND_HALF_UP (para katmanıyla tutarlı)
- RULE-038: STRATEGY_EQUIVALENCE_THRESHOLD_TL adlandırılmış sabit
- RULE-022: detect_alerts test kapsaması (4 uyarı dalı)
- RULE-031: _simulate para-korunum invariantı (total_paid = anapara + faiz)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.debt_strategy import (
    DebtItem, calc_snowball, calc_avalanche, compare_strategies,
    STRATEGY_EQUIVALENCE_THRESHOLD_TL,
)
from app.rules_engine import detect_alerts


def _debt(aid, balance, rate, minp, name="d", atype="loan"):
    return DebtItem(account_id=aid, name=name, account_type=atype,
                    balance=balance, interest_rate_monthly=rate, min_payment=minp)


# ============================================================
# RULE-025 — deterministik tie-break
# ============================================================

def test_rule025_snowball_esit_bakiye_account_id_ile_deterministik():
    """Eşit bakiyeli borçlar → snowball sırası account_id artan (DB sırasından bağımsız)."""
    debts = [_debt(3, 1000, 2.0, 100), _debt(1, 1000, 5.0, 100), _debt(2, 1000, 3.0, 100)]
    order = calc_snowball(debts).order
    # aynı bakiye → account_id'ye göre 1,2,3 (girdi 3,1,2 sırasındaydı)
    assert order == [1, 2, 3]
    # ters girdi de aynı sonucu vermeli (determinizm)
    order2 = calc_snowball(list(reversed(debts))).order
    assert order2 == [1, 2, 3]


def test_rule025_avalanche_esit_faiz_account_id_ile_deterministik():
    """Eşit faizli borçlar → avalanche sırası account_id artan."""
    debts = [_debt(3, 500, 4.0, 50), _debt(1, 900, 4.0, 50), _debt(2, 700, 4.0, 50)]
    order = calc_avalanche(debts).order
    assert order == [1, 2, 3]


# ============================================================
# RULE-033 — allocation ROUND_HALF_UP
# ============================================================

def test_rule033_percent_allocation_round_half_up():
    """105 TL'nin %2.5'i = 2.625 → ROUND_HALF_UP 2.63 (banker's 2.62 DEĞİL)."""
    from app import models
    from app.goal_rules import _compute_allocation_amount

    class _Tx:
        amount = Decimal("105")
        class transaction_type:
            value = "income"  # contribution (+)
    class _Rule:
        allocation_type = "percent"
        allocation_value = 2.5
    amount = _compute_allocation_amount(_Tx(), _Rule())
    assert amount == Decimal("2.63"), f"beklenen 2.63 (half-up), gelen {amount}"


# ============================================================
# RULE-038 — adlandırılmış eşik
# ============================================================

def test_rule038_esik_sabiti_adlandirildi():
    """Magic number 50 → STRATEGY_EQUIVALENCE_THRESHOLD_TL sabiti."""
    assert STRATEGY_EQUIVALENCE_THRESHOLD_TL == 50


# ============================================================
# RULE-022 — detect_alerts test kapsaması
# ============================================================

def test_rule022_kart_kullanim_kritik():
    a = detect_alerts(nakit=5000, kart_borcu=9700, kart_limit=10000,
                      reel_butce=1000, upcoming_payments=[], today=date(2026, 7, 18))
    assert any(x["seviye"] == "kritik" and "Kart kullanım" in x["baslik"] for x in a)


def test_rule022_kart_kullanim_uyari():
    a = detect_alerts(nakit=5000, kart_borcu=8500, kart_limit=10000,
                      reel_butce=1000, upcoming_payments=[], today=date(2026, 7, 18))
    assert any(x["seviye"] == "uyari" and "Kart kullanım" in x["baslik"] for x in a)


def test_rule022_reel_butce_negatif():
    a = detect_alerts(nakit=5000, kart_borcu=0, kart_limit=10000,
                      reel_butce=-500, upcoming_payments=[], today=date(2026, 7, 18))
    assert any(x["baslik"] == "Reel bütçe negatif" for x in a)


def test_rule022_nakit_dusuk():
    a = detect_alerts(nakit=500, kart_borcu=0, kart_limit=10000,
                      reel_butce=1000, upcoming_payments=[], today=date(2026, 7, 18))
    assert any(x["baslik"] == "Nakit çok düşük" for x in a)


def test_rule022_buyuk_odeme_7gun():
    payments = [{"tip": "kredi_taksit", "ad": "Kredi 1", "tarih": "2026-07-20", "tutar": 4000}]
    a = detect_alerts(nakit=5000, kart_borcu=0, kart_limit=10000,
                      reel_butce=1000, upcoming_payments=payments, today=date(2026, 7, 18))
    assert any("büyük ödeme" in x["baslik"] for x in a)


def test_rule022_temiz_durum_uyari_yok():
    """Sağlıklı finansal durum → hiç uyarı yok."""
    a = detect_alerts(nakit=50000, kart_borcu=1000, kart_limit=10000,
                      reel_butce=20000, upcoming_payments=[], today=date(2026, 7, 18))
    assert a == []


# ============================================================
# RULE-031 — _simulate para-korunum invariantı
# ============================================================

def test_rule031_para_korunum_invarianti():
    """
    Simülasyon sonunda: total_paid == başlangıç anapara toplamı + total_interest_paid.
    (Ödenen her kuruş ya anapara ya faiz; para yoktan var olmaz/kaybolmaz.)
    """
    debts = [_debt(1, 10000, 3.0, 2000, atype="loan"),
             _debt(2, 4000, 4.0, 500, atype="credit_card")]
    initial_principal = sum(d.balance for d in debts)
    for strat in (calc_snowball, calc_avalanche):
        r = strat(debts, extra_monthly=1000)
        # kuruş yuvarlama toleransı
        assert abs(r.total_paid - (initial_principal + r.total_interest_paid)) < 1.0, (
            f"{r.strategy}: korunum bozuk — total_paid={r.total_paid}, "
            f"anapara={initial_principal}, faiz={r.total_interest_paid}")


def test_rule031_extra_monthly_daha_hizli_bitirir():
    """Ekstra ödeme → months_to_freedom azalır (veya eşit), asla artmaz (monotonluk)."""
    debts = [_debt(1, 20000, 4.0, 1000)]
    az = calc_snowball(debts, extra_monthly=0).months_to_freedom
    cok = calc_snowball(debts, extra_monthly=2000).months_to_freedom
    assert cok <= az
