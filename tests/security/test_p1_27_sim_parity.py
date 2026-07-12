"""
P1-27 (BUG #142-145): simulation_engine ↔ gerçek executor davranış paritesi.
Sim "ne-olur" önizlemesi, gerçekte REDDEDİLECEK işlemi rosy göstermemeli.
"""
from __future__ import annotations

from datetime import date

from app.simulation_engine import _apply_action, AccountSnap, WorldSnap, DebtSnap


def _world():
    cash = AccountSnap(id=1, name="Enpara", account_type="cash", balance=5000.0)
    inv = AccountSnap(id=2, name="TLY", account_type="investment", balance=10000.0,
                      lot_count=5.0, cost_per_lot=1800.0, current_price=2000.0)
    inv_nopr = AccountSnap(id=3, name="Fiyatsiz Fon", account_type="investment",
                           balance=0.0, lot_count=5.0, cost_per_lot=1000.0, current_price=None)
    emanet = AccountSnap(id=5, name="Altin Emanet", account_type="investment",
                         balance=20000.0, is_emanet=True, lot_count=10.0, current_price=2000.0)
    debts = [
        DebtSnap(id=10, counterparty="Efe", direction="receivable", amount=3000.0,
                 due_date=date(2026, 6, 1), paid_date=None),
        DebtSnap(id=11, counterparty="Ali", direction="payable", amount=1500.0,
                 due_date=date(2026, 5, 15), paid_date=date(2026, 5, 10)),  # ZATEN ÖDENMİŞ
    ]
    return WorldSnap(as_of=date(2026, 5, 1),
                     accounts=[cash, inv, inv_nopr, emanet], incomes=[], debts=debts)


# SE-004: zaten ödenmiş borç tekrar ödenemez
def test_se004_already_paid_debt_rejected():
    world = _world()
    ok, msg = _apply_action(world, "mark_debt_paid", {"debt_id": 11})
    assert ok is False and "odenmis" in msg.lower()
    assert world.acc(1).balance == 5000.0  # nakit çift-düşmedi


def test_se004_unpaid_debt_ok():
    world = _world()
    ok, _ = _apply_action(world, "mark_debt_paid", {"debt_id": 10})  # receivable, ödenmemiş
    assert ok is True
    assert world.acc(1).balance == 8000.0  # +3000 alacak tahsil


# SE-005: geçerli fiyat yoksa satış reddedilir (sessiz 0 TL satış yok)
def test_se005_sell_without_price_rejected():
    world = _world()
    ok, msg = _apply_action(world, "sell_investment",
                            {"investment_id": 3, "lots_to_sell": 2.0})  # current_price=None
    assert ok is False and "fiyat" in msg.lower()


# SE-008: satış geliri emanet hedefe yatırılamaz
def test_se008_sell_proceeds_to_emanet_rejected():
    world = _world()
    ok, msg = _apply_action(world, "sell_investment",
                            {"investment_id": 2, "lots_to_sell": 1.0, "credit_to_account_id": 5})
    assert ok is False and "emanet" in msg.lower()
