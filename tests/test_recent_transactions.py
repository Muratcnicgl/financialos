"""
C2-lite — son işlemler cockpit'e + koç context'ine (BUG #099).
Koç analizini gerçek harcamalara dayandırsın; tutarlar cockpit'te → grounding tutarlı.
"""
from __future__ import annotations

from datetime import date

from app.models import Account, AccountType, Transaction, TransactionType
from app.rules_engine import generate_cockpit, _collect_recent_transactions
from app.coach import _build_context_message


def _tx(db, user_id, ttype, amount, category, d, desc=""):
    db.add(Transaction(user_id=user_id, transaction_type=ttype, amount=amount,
                       category=category, transaction_date=d, description=desc))


def test_son_islemler_en_yeni_ilk_ve_limitli(db_session, test_user):
    # 10 işlem farklı tarihlerde; helper son 8'i en yeni-ilk döndürmeli
    for i in range(1, 11):
        _tx(db_session, test_user.id, TransactionType.expense, i * 10.0, "market",
            date(2026, 5, i))
    db_session.commit()

    rows = _collect_recent_transactions(test_user.id, db_session, limit=8)
    assert len(rows) == 8
    # en yeni (5 Mayıs → gün 10) ilk
    assert rows[0]["tarih"] == "2026-05-10"
    assert rows[0]["tutar"] == 100.0
    assert rows[-1]["tarih"] == "2026-05-03"


def test_cockpit_son_islemler_iceriyor(db_session, test_user):
    db_session.add(Account(user_id=test_user.id, name="Enpara",
                           account_type=AccountType.cash, balance=5000.0))
    _tx(db_session, test_user.id, TransactionType.expense, 250.0, "market",
        date(2026, 5, 3), desc="haftalık alışveriş")
    db_session.commit()

    cockpit = generate_cockpit(test_user.id, date(2026, 5, 5), db_session)
    assert "son_islemler" in cockpit
    assert cockpit["son_islemler"][0]["tutar"] == 250.0
    assert cockpit["son_islemler"][0]["aciklama"] == "haftalık alışveriş"


def test_coach_context_son_islemler_blogu(db_session, test_user):
    db_session.add(Account(user_id=test_user.id, name="Enpara",
                           account_type=AccountType.cash, balance=5000.0))
    _tx(db_session, test_user.id, TransactionType.expense, 250.0, "market", date.today())
    db_session.commit()

    context, _ = _build_context_message(db_session, test_user.id)
    assert "## SON İŞLEMLER" in context
    assert "market" in context


def test_islem_yoksa_son_islemler_bos(db_session, test_user):
    context, _ = _build_context_message(db_session, test_user.id)
    assert "## SON İŞLEMLER" not in context
