"""
generate_monthly_summary (rules_engine) + coach context entegrasyonu.
Aylık matematik rules_engine'e taşındı (mimari kural); koç bu özetle trend-farkında olur.
"""
from __future__ import annotations

from datetime import date

from app.models import Account, AccountType, Transaction, TransactionType
from app.rules_engine import generate_monthly_summary
from app.coach import _build_context_message


def _tx(db, user_id, ttype, amount, category, d):
    db.add(Transaction(user_id=user_id, transaction_type=ttype, amount=amount,
                       category=category, transaction_date=d))


def test_engine_aylik_ozet_deterministik(db_session, test_user):
    _tx(db_session, test_user.id, TransactionType.income, 50000, "maas", date(2026, 5, 8))
    _tx(db_session, test_user.id, TransactionType.expense, 10000, "yemek", date(2026, 5, 3))
    _tx(db_session, test_user.id, TransactionType.expense, 8000, "yemek", date(2026, 4, 3))
    db_session.commit()

    ms = generate_monthly_summary(test_user.id, 2026, 5, db_session)
    assert ms["current"]["total_income"] == 50000.0
    assert ms["current"]["total_expense"] == 10000.0
    assert ms["current"]["net_change"] == 40000.0
    # gider 8000 -> 10000 = +25%
    assert ms["trend"]["expense_delta_pct"] == 25.0
    assert ms["period"]["label"] == "Mayıs 2026"


def test_engine_ocak_onceki_ay_gecen_yil_aralik(db_session, test_user):
    """Ocak'ın önceki ayı geçen yılın Aralık'ı olmalı (yıl sınırı)."""
    ms = generate_monthly_summary(test_user.id, 2026, 1, db_session)
    assert ms["previous_period"]["year"] == 2025
    assert ms["previous_period"]["month"] == 12
    assert ms["previous_period"]["label"] == "Aralık 2025"


def test_coach_context_bu_ay_blogu(db_session, test_user):
    """Bu ay (bugün tarihli) işlem varsa koç context'inde '## BU AY' bloğu görünür."""
    acc = Account(user_id=test_user.id, name="Enpara", account_type=AccountType.cash, balance=5000.0)
    db_session.add(acc)
    db_session.commit()
    # bugün tarihli işlem → her zaman içinde bulunulan ay (deterministik)
    _tx(db_session, test_user.id, TransactionType.expense, 250, "market", date.today())
    db_session.commit()

    context, _cockpit = _build_context_message(db_session, test_user.id)
    assert "## BU AY" in context
    assert "Gider" in context


def test_coach_context_islem_yoksa_bu_ay_yok(db_session, test_user):
    """Bu ay hiç işlem yoksa '## BU AY' bloğu eklenmez (gürültü yok)."""
    acc = Account(user_id=test_user.id, name="Enpara", account_type=AccountType.cash, balance=5000.0)
    db_session.add(acc)
    db_session.commit()
    context, _ = _build_context_message(db_session, test_user.id)
    assert "## BU AY" not in context
