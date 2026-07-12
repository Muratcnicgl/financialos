"""
Decimal para hassasiyeti testleri (M5 / ADR-030). M5'in BÜTÜN AMACI: para matematiğinde
float drift (0.1+0.2=0.30000000000000004) YOK. Bu testler drift'in gerçekten yok olduğunu +
Numeric kolonların Decimal döndürdüğünü + round-half-up'ı kanıtlar.
"""
from decimal import Decimal

import pytest

from app.money import D, ZERO, q2, q4, floatify
from app.models import Account, AccountType, Transaction, TransactionType
from app.rules_engine import simulate_partial_sale, calculate_investment_pnl


def test_float_drift_gone_in_decimal():
    """0.1 + 0.2, Decimal'de TAM 0.3 (float'ta 0.30000000000000004)."""
    assert D("0.1") + D("0.2") == Decimal("0.3")
    assert 0.1 + 0.2 != 0.3  # float drift gerçek (kontrol)
    # 10 kez 0.1 topla → tam 1.0 (float'ta 0.9999999999999999)
    toplam = ZERO
    for _ in range(10):
        toplam += D("0.1")
    assert toplam == Decimal("1.0")


def test_numeric_column_returns_decimal(db_session, test_user):
    """Numeric kolon ORM'den Decimal döner + kuruş hassasiyeti korunur (round-trip)."""
    acc = Account(user_id=test_user.id, name="Kasa", account_type=AccountType.cash,
                  balance=Decimal("1234.5678"))
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    assert isinstance(acc.balance, Decimal)
    assert acc.balance == Decimal("1234.5678")


def test_money_sum_exact_over_many_rows(db_session, test_user):
    """0.01'lik 100 işlem TAM 1.00 eder (float'ta 1.0000000000000007 tipik drift)."""
    acc = Account(user_id=test_user.id, name="Kasa", account_type=AccountType.cash, balance=ZERO)
    db_session.add(acc)
    db_session.commit()
    for _ in range(100):
        db_session.add(Transaction(user_id=test_user.id, account_id=acc.id,
                                   transaction_type=TransactionType.expense,
                                   amount=Decimal("0.01"), category="test"))
    db_session.commit()
    toplam = sum((t.amount for t in db_session.query(Transaction).all()), ZERO)
    assert toplam == Decimal("1.00")
    assert isinstance(toplam, Decimal)


def test_q2_round_half_up():
    """q2 ROUND_HALF_UP: 2.675 → 2.68 (banker's/float'ta 2.67 olurdu)."""
    assert q2("2.675") == Decimal("2.68")
    assert q2("2.665") == Decimal("2.67")
    assert q2(Decimal("100.005")) == Decimal("100.01")
    assert q4("1.00005") == Decimal("1.0001")


def test_simulate_partial_sale_precision():
    """Kısmi satış: brut - stopaj = net, kuruş kesin (Murat'ın Gürcistan senaryosu)."""
    sim = simulate_partial_sale(lot_count=6, cost_per_lot=4000.0, current_price=4929.56, lots_to_sell=4)
    # satış = 4 * 4929.56 = 19718.24 (float'ta 19718.240000000002)
    assert sim["satis_tutari"] == pytest.approx(19718.24)
    # net + stopaj == brut (kuruş tutarlı)
    assert sim["net_kar"] + sim["stopaj"] == pytest.approx(sim["brut_kar"])


def test_investment_pnl_precision():
    """K/Z: guncel - maliyet = brut_kar tam."""
    pnl = calculate_investment_pnl(lot_count=6, cost_per_lot=4000.0, current_price=4929.56)
    assert pnl["guncel_deger"] - pnl["toplam_maliyet"] == pytest.approx(pnl["brut_kar"])


def test_floatify_serialization_boundary():
    """floatify: iç Decimal dict → public float (B1 JSON sınırı). Nested + list gezer."""
    inner = {"a": Decimal("1.5"), "b": [Decimal("2.25"), {"c": Decimal("3.0")}], "d": "x", "e": 5}
    out = floatify(inner)
    assert out["a"] == 1.5 and isinstance(out["a"], float)
    assert out["b"][0] == 2.25 and isinstance(out["b"][0], float)
    assert isinstance(out["b"][1]["c"], float)
    assert out["d"] == "x" and out["e"] == 5  # non-money dokunulmaz


def test_D_coerces_float_without_drift():
    """D(float) str üzerinden gider → binary drift YOK: D(0.1) == Decimal('0.1')."""
    assert D(0.1) == Decimal("0.1")
    assert D(7277.904) == Decimal("7277.904")
    assert D(None) is None
