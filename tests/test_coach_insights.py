"""
tests/test_coach_insights.py

Wave-2 Hafta 1 Davranissal Hafiza extractor'lari icin birim testleri.

Adaptasyon notu:
- ActionHistory.status yok; success=True -> executed, success=False -> excluded
- ActionHistory.applied_at kullanilir (created_at yok); summary zorunlu
- User modeli email alani icermez
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.coach_insights import (
    extract_decision_rhythm,
    DECISION_RHYTHM_MIN_ACTIONS,
    DECISION_RHYTHM_DOMINANT_RATIO,
)
from app.models import CoachInsight, ActionHistory


class TestDecisionRhythm:
    """decision_rhythm extractor'i icin 6 senaryo testi."""

    def test_insufficient_sample_no_insight(self, db_session, test_user):
        """4 aksiyon (min 5) -> insight olusmamali."""
        for i in range(4):
            db_session.add(ActionHistory(
                user_id=test_user.id,
                action_type="add_transaction",
                payload="{}",
                summary="test",
                success=True,
                applied_at=datetime.utcnow() - timedelta(days=i),
            ))
        db_session.commit()

        extract_decision_rhythm(db_session, test_user.id)

        insights = db_session.execute(
            select(CoachInsight).where(
                CoachInsight.user_id == test_user.id,
                CoachInsight.insight_type == "decision_rhythm",
            )
        ).scalars().all()
        assert len(insights) == 0

    def test_dominant_aksam_creates_insight(self, db_session, test_user):
        """10 aksiyon, 7'si aksam -> 'aksam' dominant insight."""
        for i in range(7):
            dt = datetime.utcnow().replace(hour=20, minute=0) - timedelta(days=i)
            db_session.add(ActionHistory(
                user_id=test_user.id,
                action_type="add_transaction",
                payload="{}",
                summary="test",
                success=True,
                applied_at=dt,
            ))
        for i in range(3):
            dt = datetime.utcnow().replace(hour=13, minute=0) - timedelta(days=i + 7)
            db_session.add(ActionHistory(
                user_id=test_user.id,
                action_type="add_transaction",
                payload="{}",
                summary="test",
                success=True,
                applied_at=dt,
            ))
        db_session.commit()

        extract_decision_rhythm(db_session, test_user.id)

        insights = db_session.execute(
            select(CoachInsight).where(
                CoachInsight.user_id == test_user.id,
                CoachInsight.insight_type == "decision_rhythm",
            )
        ).scalars().all()

        assert len(insights) == 1
        assert "aksam" in insights[0].title
        assert insights[0].confidence_basis == "pattern_grounded"
        assert insights[0].evidence_count == 1
        assert insights[0].status == "active"

    def test_balanced_distribution_no_insight(self, db_session, test_user):
        """8 aksiyon her dilime esit (2'ser) -> dominant yok, insight olusmamali.

        UTC saatleri UTC+3 (Turkiye) sonrasi da farkli slot'lara dusuyor:
          UTC 1  -> local 4  -> gece
          UTC 7  -> local 10 -> sabah
          UTC 13 -> local 16 -> ogle
          UTC 19 -> local 22 -> aksam
        """
        slot_hours = {"gece": 1, "sabah": 7, "ogle": 13, "aksam": 19}
        action_idx = 0
        for slot, hour in slot_hours.items():
            for i in range(2):
                action_idx += 1
                dt = datetime.utcnow().replace(
                    hour=hour, minute=0
                ) - timedelta(days=action_idx)
                db_session.add(ActionHistory(
                    user_id=test_user.id,
                    action_type="add_transaction",
                    payload="{}",
                    summary="test",
                    success=True,
                    applied_at=dt,
                ))
        db_session.commit()

        extract_decision_rhythm(db_session, test_user.id)

        insights = db_session.execute(
            select(CoachInsight).where(
                CoachInsight.user_id == test_user.id,
                CoachInsight.insight_type == "decision_rhythm",
            )
        ).scalars().all()
        assert len(insights) == 0

    def test_failed_actions_excluded(self, db_session, test_user):
        """success=False olan aksiyonlar sayilmamali; sadece success=True ogle'de."""
        for i in range(5):
            dt = datetime.utcnow().replace(hour=20) - timedelta(days=i)
            db_session.add(ActionHistory(
                user_id=test_user.id,
                action_type="add_transaction",
                payload="{}",
                summary="test",
                success=False,  # excluded
                applied_at=dt,
            ))
        for i in range(5):
            dt = datetime.utcnow().replace(hour=13) - timedelta(days=i + 5)
            db_session.add(ActionHistory(
                user_id=test_user.id,
                action_type="add_transaction",
                payload="{}",
                summary="test",
                success=True,
                applied_at=dt,
            ))
        db_session.commit()

        extract_decision_rhythm(db_session, test_user.id)

        insights = db_session.execute(
            select(CoachInsight).where(
                CoachInsight.user_id == test_user.id,
                CoachInsight.insight_type == "decision_rhythm",
            )
        ).scalars().all()
        assert len(insights) == 1
        assert "ogle" in insights[0].title

    def test_old_actions_excluded(self, db_session, test_user):
        """30+ gunden eski aksiyonlar sayilmamali."""
        for i in range(5):
            dt = datetime.utcnow().replace(hour=3) - timedelta(days=40 + i)
            db_session.add(ActionHistory(
                user_id=test_user.id,
                action_type="add_transaction",
                payload="{}",
                summary="test",
                success=True,
                applied_at=dt,
            ))
        for i in range(5):
            dt = datetime.utcnow().replace(hour=20) - timedelta(days=i + 1)
            db_session.add(ActionHistory(
                user_id=test_user.id,
                action_type="add_transaction",
                payload="{}",
                summary="test",
                success=True,
                applied_at=dt,
            ))
        db_session.commit()

        extract_decision_rhythm(db_session, test_user.id)

        insights = db_session.execute(
            select(CoachInsight).where(
                CoachInsight.user_id == test_user.id,
                CoachInsight.insight_type == "decision_rhythm",
            )
        ).scalars().all()
        assert len(insights) == 1
        assert "aksam" in insights[0].title

    def test_idempotent_rerun(self, db_session, test_user):
        """Ayni veriyle 2 kez calistir -> evidence_count=2 (UPSERT)."""
        for i in range(7):
            dt = datetime.utcnow().replace(hour=20) - timedelta(days=i)
            db_session.add(ActionHistory(
                user_id=test_user.id,
                action_type="add_transaction",
                payload="{}",
                summary="test",
                success=True,
                applied_at=dt,
            ))
        db_session.commit()

        extract_decision_rhythm(db_session, test_user.id)
        extract_decision_rhythm(db_session, test_user.id)

        insights = db_session.execute(
            select(CoachInsight).where(
                CoachInsight.user_id == test_user.id,
                CoachInsight.insight_type == "decision_rhythm",
            )
        ).scalars().all()

        assert len(insights) == 1
        assert insights[0].evidence_count == 2