"""
BUG #109 — koç context'inde BORÇ ÖZGÜRLÜĞÜ (Borç Çığı/avalanche) özeti.
Kurucu 5-kredi durumunda koç proaktif payoff yolu gösterebilsin (deterministik debt_strategy).
"""
from __future__ import annotations

from datetime import date

from app.models import Account, AccountType
from app.coach import _build_context_message


def test_109_borc_varsa_ozgurluk_blogu(db_session, test_user):
    db_session.add(Account(user_id=test_user.id, name="Enpara Kredi",
                           account_type=AccountType.loan, balance=50000.0,
                           monthly_payment=2500.0, interest_rate=1.5,
                           remaining_installments=24))
    db_session.add(Account(user_id=test_user.id, name="Nakit",
                           account_type=AccountType.cash, balance=5000.0))
    db_session.commit()

    context, _ = _build_context_message(db_session, test_user.id)
    assert "## BORÇ ÖZGÜRLÜĞÜ" in context
    assert "Enpara Kredi" in context
    assert "Öncelik sırası" in context


def test_109_borc_yoksa_blok_yok(db_session, test_user):
    db_session.add(Account(user_id=test_user.id, name="Nakit",
                           account_type=AccountType.cash, balance=5000.0))
    db_session.commit()
    context, _ = _build_context_message(db_session, test_user.id)
    assert "## BORÇ ÖZGÜRLÜĞÜ" not in context
