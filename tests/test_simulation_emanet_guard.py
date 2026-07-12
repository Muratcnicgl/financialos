"""
BUG #101 — simülasyon MC1 emanet guard'ı (executor ile tutarlılık).
Gerçek executor emanet hesaba add_transaction/update_account_balance'i bloklar; sim de
bloklamalı ki "ne-olur" önizlemesi gerçekte reddedilecek işlemi rosy göstermesin.
update_fund_price bloklanmaz (revalüasyon meşru; executor da bloklamıyor).
"""
from __future__ import annotations

from datetime import date

from app.simulation_engine import _apply_action, AccountSnap, WorldSnap


def _world_with_emanet() -> WorldSnap:
    cash = AccountSnap(id=1, name="Enpara", account_type="cash", balance=5000.0)
    emanet = AccountSnap(id=5, name="Altın Emanet", account_type="investment",
                         balance=20000.0, is_emanet=True, lot_count=10, current_price=2000.0)
    return WorldSnap(as_of=date(2026, 5, 1), accounts=[cash, emanet], incomes=[], debts=[])


def test_add_transaction_emanet_bloklanir():
    world = _world_with_emanet()
    ok, msg = _apply_action(world, "add_transaction", {
        "account_id": 5, "amount": 100.0, "transaction_type": "expense",
        "auto_update_balance": True,
    })
    assert ok is False
    assert "emanet" in msg.lower()


def test_update_account_balance_emanet_bloklanir():
    world = _world_with_emanet()
    ok, msg = _apply_action(world, "update_account_balance", {
        "account_id": 5, "new_balance": 0.0,
    })
    assert ok is False
    assert "emanet" in msg.lower()
    # bakiye değişmedi
    assert world.acc(5).balance == 20000.0


def test_normal_hesaba_islem_calisir():
    """Kontrol: emanet olmayan hesapta işlem eskisi gibi çalışır."""
    world = _world_with_emanet()
    ok, _ = _apply_action(world, "add_transaction", {
        "account_id": 1, "amount": 100.0, "transaction_type": "expense",
        "auto_update_balance": True,
    })
    assert ok is True
    assert world.acc(1).balance == 4900.0


def test_update_fund_price_emanet_meshru():
    """Emanet revalüasyonu (fiyat güncelleme) bloklanmaz — executor da bloklamıyor."""
    world = _world_with_emanet()
    ok, _ = _apply_action(world, "update_fund_price", {
        "account_id": 5, "new_price": 2500.0,
    })
    assert ok is True
    assert world.acc(5).current_price == 2500.0
