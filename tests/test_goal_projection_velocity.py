"""
BUG #105 — goal tamamlanma projeksiyonu GERÇEK katkı süresini kullanır (sabit 90 değil).
Genç goal'de sabit 90'a bölmek hızı düşük gösterip tamamlanmayı çok uzağa atıyordu.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from app.models import Goal, GoalAllocation, Transaction, TransactionType
from app.goal_engine import _project_cash_completion


def test_105_genc_goal_gercek_span_ile_projekte(db_session, test_user):
    # Hedef 30000, şu ana dek 3000 birikmiş; katkı 10 gün önce yapılmış.
    goal = Goal(user_id=test_user.id, goal_type="cash_target", title="Tatil",
                target_amount=Decimal("30000"), current_amount=Decimal("3000"), status="active")
    db_session.add(goal)
    db_session.commit()

    tx = Transaction(user_id=test_user.id, transaction_type=TransactionType.income,
                     amount=3000.0, category="tasarruf", transaction_date=date.today())
    db_session.add(tx)
    db_session.commit()

    alloc = GoalAllocation(goal_id=goal.id, transaction_id=tx.id, amount=Decimal("3000"))
    alloc.created_at = datetime.utcnow() - timedelta(days=10)  # 10 gün önce
    db_session.add(alloc)
    db_session.commit()

    result = _project_cash_completion(goal, Decimal("3000"), db_session)
    assert result is not None
    days_out = (result - date.today()).days
    # span=10 → günlük ~300 → kalan 27000 / 300 ≈ 90 gün. Sabit /90 olsaydı ~810 gün.
    assert 70 <= days_out <= 110, f"beklenen ~90 gün, gelen {days_out} (sabit-90 regresyonu?)"


def test_105_katki_yoksa_none(db_session, test_user):
    goal = Goal(user_id=test_user.id, goal_type="cash_target", title="Tatil",
                target_amount=Decimal("30000"), current_amount=Decimal("0"), status="active")
    db_session.add(goal)
    db_session.commit()
    assert _project_cash_completion(goal, Decimal("0"), db_session) is None
