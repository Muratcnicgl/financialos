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
    extract_mc_reference_frequency,
    extract_decision_rhythm,
    DECISION_RHYTHM_MIN_ACTIONS,
    DECISION_RHYTHM_DOMINANT_RATIO,
)
from app.models import CoachInsight, ActionHistory, CoachMemory


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


# ============================================================
# TESTS: mc_reference_frequency
# ============================================================

def _make_assistant_msg(db_session, user_id, content, hours_ago=1):
    """Helper: belirli zamanda role=assistant CoachMemory satiri."""
    msg = CoachMemory(
        user_id=user_id,
        role="assistant",
        content=content,
        timestamp=datetime.utcnow() - timedelta(hours=hours_ago),
    )
    db_session.add(msg)
    db_session.commit()
    return msg


def test_mc_freq_insufficient_sample(db_session, test_user):
    """5 mesaj < 10 esigi -> hicbir insight uretilmemeli."""
    for i in range(5):
        _make_assistant_msg(db_session, test_user.id, f"MC8 kurali ile {i}", hours_ago=i+1)

    result = extract_mc_reference_frequency(db_session, test_user.id)

    assert result["skipped_reason"] is not None
    assert "insufficient_sample" in result["skipped_reason"]
    assert result["created"] == 0

    insights = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="mc_reference_frequency",
    ).all()
    assert len(insights) == 0


def test_mc_freq_dominant_mc(db_session, test_user):
    """10 mesajdan 8'i MC8 iceriyor -> MC8 rank 1, sort_priority=10, status=active.
    MC1 ve MC3 birer kez -> top 3'e girerler. MC2/4/5/6/7 dormant."""
    for i in range(8):
        _make_assistant_msg(db_session, test_user.id, f"MC8 (Hayatta Kalma) gerekli {i}", hours_ago=i+1)
    _make_assistant_msg(db_session, test_user.id, "MC1 nakit oncelik", hours_ago=9)
    _make_assistant_msg(db_session, test_user.id, "MC3 borc disiplini", hours_ago=10)

    result = extract_mc_reference_frequency(db_session, test_user.id)

    assert result["skipped_reason"] is None
    assert result["total_messages"] == 10
    assert result["mc_counts"]["8"] == 8
    assert result["mc_counts"]["1"] == 1
    assert result["mc_counts"]["3"] == 1

    mc8_active = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="mc_reference_frequency",
        title="MC8 sik referans verilen kural",
    ).first()
    assert mc8_active is not None
    assert mc8_active.status == "active"
    assert mc8_active.sort_priority == 10
    assert mc8_active.evidence_count == 8
    assert mc8_active.confidence_basis == "pattern_grounded"

    dormant = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="mc_reference_frequency",
        status="dormant",
    ).all()
    dormant_titles = {ins.title for ins in dormant}
    assert "MC2 hic kullanilmayan kural" in dormant_titles
    assert "MC4 hic kullanilmayan kural" in dormant_titles
    assert len(dormant) == 5  # MC2, MC4, MC5, MC6, MC7


def test_mc_freq_balanced_tiebreak(db_session, test_user):
    """4 MC esit dagilmis (3'er kez). Tie-break: MC numarasi kucuk olan oncelikli.
    MC1, MC2, MC3 top 3 -> active. MC4 ne aktif ne dormant (orta seviye yok sayilir).
    MC5, MC6, MC7, MC8 dormant."""
    for mc_num in [1, 2, 3, 4]:
        for i in range(3):
            _make_assistant_msg(
                db_session, test_user.id,
                f"MC{mc_num} aciklama {i}",
                hours_ago=mc_num*5 + i,
            )

    result = extract_mc_reference_frequency(db_session, test_user.id)
    assert result["total_messages"] == 12

    active = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="mc_reference_frequency",
        status="active",
    ).all()
    active_titles = {ins.title for ins in active}
    assert active_titles == {
        "MC1 sik referans verilen kural",
        "MC2 sik referans verilen kural",
        "MC3 sik referans verilen kural",
    }

    mc4_any = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="mc_reference_frequency",
    ).filter(CoachInsight.title.like("MC4%")).all()
    assert len(mc4_any) == 0

    dormant = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="mc_reference_frequency",
        status="dormant",
    ).all()
    assert len(dormant) == 4


def test_mc_freq_idempotent_rerun(db_session, test_user):
    """Ayni veriyle 2 kez calistir -> insight sayisi degismez,
    last_seen_at her seferinde guncellenir, evidence_count tutarli."""
    import time as _time

    for i in range(8):
        _make_assistant_msg(db_session, test_user.id, f"MC8 mesaj {i}", hours_ago=i+1)
    for i in range(2):
        _make_assistant_msg(db_session, test_user.id, f"MC1 mesaj {i}", hours_ago=20+i)

    result1 = extract_mc_reference_frequency(db_session, test_user.id)
    count_after_first = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="mc_reference_frequency",
    ).count()

    mc8_first = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="MC8 sik referans verilen kural",
    ).first()
    last_seen_first = mc8_first.last_seen_at

    _time.sleep(0.05)

    result2 = extract_mc_reference_frequency(db_session, test_user.id)
    count_after_second = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="mc_reference_frequency",
    ).count()

    assert count_after_first == count_after_second
    assert result2["created"] == 0
    assert result2["updated"] == result1["created"]

    db_session.refresh(mc8_first)
    assert mc8_first.evidence_count == 8

    assert mc8_first.last_seen_at > last_seen_first

