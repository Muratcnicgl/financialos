"""
Zikzak projeksiyonu — "bugün harcamazsan yarınki limit" (BUG #100).
Kurucu "biriken güç" mekaniği. ADR-026 ile tutarlı: additive değil, aynı bütçenin
bir gün az güne bölünmesi (çift-sayım yok).
"""
from __future__ import annotations

from datetime import date

from app.models import Account, AccountType
from app.rules_engine import generate_cockpit


def _cash(db, user_id, balance=6000.0):
    db.add(Account(user_id=user_id, name="Enpara", account_type=AccountType.cash, balance=balance))
    db.commit()


def test_yarin_limit_harcamasiz_formul_tutarli(db_session, test_user):
    _cash(db_session, test_user.id, 6000.0)
    cockpit = generate_cockpit(test_user.id, date(2026, 5, 20), db_session)
    dr = cockpit["days_remaining"]
    rb = cockpit["reel_butce"]
    assert dr > 1
    # yarınki limit = aynı bütçe / (kalan gün - 1)
    assert cockpit["yarin_limit_harcamasiz"] == round(rb / (dr - 1), 2)


def test_bugun_harcamazsan_yarin_limit_artar(db_session, test_user):
    """Zikzak özü: bugün 0 harcarsan yarınki limit BUGÜNKÜNDEN yüksek olur."""
    _cash(db_session, test_user.id, 6000.0)
    cockpit = generate_cockpit(test_user.id, date(2026, 5, 20), db_session)
    assert cockpit["yarin_limit_harcamasiz"] > cockpit["daily_limit"]


def test_son_gun_yarin_limit_tum_butce(db_session, test_user):
    """Ayın son günü: days_remaining=1 → yarın limiti tüm kalan bütçe."""
    _cash(db_session, test_user.id, 6000.0)
    cockpit = generate_cockpit(test_user.id, date(2026, 5, 31), db_session)
    assert cockpit["days_remaining"] == 1
    assert cockpit["yarin_limit_harcamasiz"] == cockpit["reel_butce"]
