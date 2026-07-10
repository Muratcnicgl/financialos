"""
A1 tamamlama — kredi kartı SON ÖDEME proaktif hatırlatması (BUG #096).
Kurucu vizyon: Ziraat kart son ödeme günü yaklaşıp borç varken koç proaktif uyarmalı
(kart %99.8 doluyken hayati). Deterministik — izole in-memory DB.
"""
from __future__ import annotations

from datetime import date

from app.models import Account, AccountType
from app.rules_engine import _collect_upcoming_reminders


def _card(db, user_id, *, balance, payment_day, credit_limit=12000.0, name="Ziraat"):
    a = Account(user_id=user_id, name=name, account_type=AccountType.credit_card,
                balance=balance, payment_day=payment_day, statement_day=2,
                credit_limit=credit_limit)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_096_kart_son_odeme_yaklasinca_hatirlatilir(db_session, test_user):
    """payment_day 7 gün içinde + borç var → card_payment reminder."""
    today = date(2026, 5, 7)   # son ödeme 12'sinde → 5 gün sonra
    card = _card(db_session, test_user.id, balance=11976.0, payment_day=12)
    accounts = [card]

    reminders = _collect_upcoming_reminders(test_user.id, today, db_session, accounts, kart_borcu=11976.0)

    cp = [r for r in reminders if r["type"] == "card_payment"]
    assert len(cp) == 1
    assert cp[0]["days_until"] == 5
    assert cp[0]["amount"] == 11976.0
    assert cp[0]["card_risk"] is True
    assert "son ödeme" in cp[0]["name"].lower()


def test_096_borc_yoksa_hatirlatma_yok(db_session, test_user):
    """Kart borcu 0 → son ödeme hatırlatması üretilmez."""
    today = date(2026, 5, 7)
    card = _card(db_session, test_user.id, balance=0.0, payment_day=12)
    reminders = _collect_upcoming_reminders(test_user.id, today, db_session, [card], kart_borcu=0.0)
    assert [r for r in reminders if r["type"] == "card_payment"] == []


def test_096_son_odeme_uzaksa_hatirlatma_yok(db_session, test_user):
    """payment_day 7 günden uzak → hatırlatma yok."""
    today = date(2026, 5, 1)   # son ödeme 12'sinde → 11 gün sonra (>7)
    card = _card(db_session, test_user.id, balance=5000.0, payment_day=12)
    reminders = _collect_upcoming_reminders(test_user.id, today, db_session, [card], kart_borcu=5000.0)
    assert [r for r in reminders if r["type"] == "card_payment"] == []


def test_096_kart_odeme_oncelikte_basa_gelir(db_session, test_user):
    """card_risk=True olduğu için kart son ödeme, düşük-öncelikli kalemlerin önüne geçer."""
    today = date(2026, 5, 10)   # son ödeme 12 → 2 gün sonra
    card = _card(db_session, test_user.id, balance=11976.0, payment_day=12)
    reminders = _collect_upcoming_reminders(test_user.id, today, db_session, [card], kart_borcu=11976.0)
    assert reminders, "en az kart ödeme hatırlatması olmalı"
    assert reminders[0]["type"] == "card_payment"
