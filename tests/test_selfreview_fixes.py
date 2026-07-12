"""
Öz-denetim (self-review) bulguları düzeltmeleri — BUG #110, #102-sim.

#110: BU AY / BORÇ ÖZGÜRLÜĞÜ koç context sayıları cockpit'te olmadığı için grounding
onları "izlenemeyen" sanıp analiz raporunda confidence'ı düşürüyordu (yanlış-pozitif).
#102-sim: sim sell_investment current_price'ı güncellemiyordu (executor ile tutarsız).
"""
from __future__ import annotations

from datetime import date

from app.models import Account, AccountType, Transaction, TransactionType
from app.coach import _build_context_message
from app.grounding import check_grounding
from app.simulation_engine import _apply_action, AccountSnap, WorldSnap


def test_110_aylik_ozet_sayilari_grounding_dogrular(db_session, test_user):
    db_session.add(Account(user_id=test_user.id, name="Enpara",
                           account_type=AccountType.cash, balance=5000.0))
    # bu ay (bugün) 1234 TL gider → aylık total_expense = 1234
    db_session.add(Transaction(user_id=test_user.id, transaction_type=TransactionType.expense,
                               amount=1234.0, category="market", transaction_date=date.today()))
    db_session.commit()

    context, cockpit = _build_context_message(db_session, test_user.id)
    assert "_coach_extra_numbers" in cockpit
    # Koç "bu ay giderin 1.234 TL" derse grounding DOĞRULANMIŞ saymalı (yanlış-pozitif yok)
    r = check_grounding("Bu ay toplam giderin 1.234 TL oldu.", cockpit)
    assert r["ok"] is True, f"aylık gider grounding'de doğrulanmalı: {r}"


def test_110_borc_faizi_grounding_dogrular(db_session, test_user):
    db_session.add(Account(user_id=test_user.id, name="Kredi",
                           account_type=AccountType.loan, balance=50000.0,
                           monthly_payment=2500.0, interest_rate=1.5, remaining_installments=24))
    db_session.commit()
    context, cockpit = _build_context_message(db_session, test_user.id)
    # borç bakiyesi (50.000) grounding'de olmalı
    assert 50000.0 in cockpit.get("_coach_extra_numbers", [])


def test_102_sim_sell_current_price_guncellenir():
    inv = AccountSnap(id=5, name="TLY", account_type="investment", balance=10000.0,
                      lot_count=10, cost_per_lot=800.0, current_price=1000.0, is_emanet=False)
    cash = AccountSnap(id=1, name="Enpara", account_type="cash", balance=0.0)
    world = WorldSnap(as_of=date(2026, 5, 1), accounts=[inv, cash], incomes=[], debts=[])

    ok, _ = _apply_action(world, "sell_investment", {
        "investment_id": 5, "lots_to_sell": 4, "actual_price": 1200.0,
        "credit_to_account_id": 1,
    })
    assert ok is True
    # kalan 6 lot taze fiyattan (1200) değerlenmeli → executor ile tutarlı
    assert world.acc(5).current_price == 1200.0
    assert world.acc(5).balance == 6 * 1200.0
    assert world.acc(5).balance == world.acc(5).lot_count * world.acc(5).current_price
