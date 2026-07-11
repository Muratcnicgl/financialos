"""
RULE-008: simulate_partial_sale giriş doğrulaması (negatif/sıfır lot, negatif fiyat/maliyet).
"""
from __future__ import annotations

import pytest

from app.rules_engine import simulate_partial_sale


def test_sifir_veya_negatif_lot_reddedilir():
    with pytest.raises(ValueError):
        simulate_partial_sale(lot_count=10, cost_per_lot=100, current_price=120, lots_to_sell=0)
    with pytest.raises(ValueError):
        simulate_partial_sale(lot_count=10, cost_per_lot=100, current_price=120, lots_to_sell=-3)


def test_negatif_fiyat_maliyet_reddedilir():
    with pytest.raises(ValueError):
        simulate_partial_sale(lot_count=10, cost_per_lot=100, current_price=-5, lots_to_sell=2)
    with pytest.raises(ValueError):
        simulate_partial_sale(lot_count=10, cost_per_lot=-100, current_price=120, lots_to_sell=2)


def test_fazla_lot_hala_reddedilir():
    with pytest.raises(ValueError):
        simulate_partial_sale(lot_count=5, cost_per_lot=100, current_price=120, lots_to_sell=6)


def test_gecerli_giris_calisir():
    r = simulate_partial_sale(lot_count=10, cost_per_lot=100, current_price=120, lots_to_sell=4)
    assert r["satilan_lot"] == 4
