"""
A1 tamamlama — vadesi yaklaşan ALACAK (receivable) proaktif hatırlatması (BUG #119).
Roadmap A1: "alacak (Efe vb.) tarihleri yaklaşınca koç proaktif." Nakit dar olduğundan
zamanında tahsilat solvency-kritik. Deterministik — izole in-memory DB.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.models import PersonalDebt, DebtDirection
from app.rules_engine import _collect_upcoming_reminders


def _receivable(db, user_id, *, counterparty="Efe", amount=2000.0, due_in_days=3,
                is_paid=False, today=date(2026, 5, 7)):
    d = PersonalDebt(
        user_id=user_id, counterparty=counterparty, direction=DebtDirection.receivable,
        amount=amount, is_paid=is_paid, due_date=today + timedelta(days=due_in_days),
    )
    db.add(d); db.commit(); db.refresh(d)
    return d


def test_119_vadesi_yaklasan_alacak_hatirlatilir(db_session, test_user):
    today = date(2026, 5, 7)
    _receivable(db_session, test_user.id, amount=2000.0, due_in_days=3, today=today)

    reminders = _collect_upcoming_reminders(test_user.id, today, db_session, [], kart_borcu=0.0)

    rec = [r for r in reminders if r["type"] == "receivable"]
    assert len(rec) == 1
    assert rec[0]["days_until"] == 3
    assert rec[0]["amount"] == 2000.0
    assert rec[0]["card_risk"] is False          # risk değil, giriş fırsatı
    assert "Efe" in rec[0]["name"]
    assert "alacağ" in rec[0]["name"].lower()


def test_119_odenmis_alacak_hatirlatilmaz(db_session, test_user):
    today = date(2026, 5, 7)
    _receivable(db_session, test_user.id, is_paid=True, due_in_days=2, today=today)
    reminders = _collect_upcoming_reminders(test_user.id, today, db_session, [], kart_borcu=0.0)
    assert [r for r in reminders if r["type"] == "receivable"] == []


def test_119_uzak_vadeli_alacak_hatirlatilmaz(db_session, test_user):
    today = date(2026, 5, 7)
    _receivable(db_session, test_user.id, due_in_days=20, today=today)   # 20 > 7
    reminders = _collect_upcoming_reminders(test_user.id, today, db_session, [], kart_borcu=0.0)
    assert [r for r in reminders if r["type"] == "receivable"] == []


def test_119_bugun_vadeli_alacak_hatirlatilir(db_session, test_user):
    """days_until == 0 (bugün) sınır dâhil olmalı."""
    today = date(2026, 5, 7)
    _receivable(db_session, test_user.id, due_in_days=0, today=today)
    reminders = _collect_upcoming_reminders(test_user.id, today, db_session, [], kart_borcu=0.0)
    rec = [r for r in reminders if r["type"] == "receivable"]
    assert len(rec) == 1 and rec[0]["days_until"] == 0
