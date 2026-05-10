"""
tests/test_coach_insights.py

Wave-2 Hafta 1 Davranissal Hafiza extractor'lari icin birim testleri.

Adaptasyon notu:
- ActionHistory.status yok; success=True -> executed, success=False -> excluded
- ActionHistory.applied_at kullanilir (created_at yok); summary zorunlu
- User modeli email alani icermez
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.coach_insights import (
    extract_mc_reference_frequency,
    extract_decision_rhythm,
    DECISION_RHYTHM_MIN_ACTIONS,
    DECISION_RHYTHM_DOMINANT_RATIO,
    extract_question_typology,
    QT_PCT_OPEN_THRESHOLD,
    QT_RQ_THRESHOLD,
    QT_HEALTHY_PRIORITY,
    QT_WARNING_PRIORITY,
    extract_category_account_preference,
    CAP_DOMINANT_THRESHOLD,
    CAP_MIN_TRANSACTIONS,
    CAP_DOMINANT_PRIORITY,
    extract_action_rejection_pattern,
    ARP_REJECTION_THRESHOLD,
    ARP_MIN_RESOLVED,
    ARP_DOMINANT_PRIORITY,
    extract_breakthrough,
    BT_NET_WORTH_THRESHOLD_TL,
    BT_DEBT_REDUCTION_THRESHOLD_TL,
    BT_INVESTMENT_GROWTH_THRESHOLD_TL,
    BT_DOMINANT_PRIORITY,
    BT_MIN_SNAPSHOTS_RECENT,
    BT_MIN_SNAPSHOTS_BASELINE,
)
from app.models import (
    CoachInsight, ActionHistory, CoachMemory,
    Transaction, TransactionType, Account,
    PendingAction, ActionStatus, NetWorthSnapshot,
)


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


# ============================================================
# TESTS: question_typology
# ============================================================

def _qt_msg(db_session, user_id, content, hours_ago=1):
    msg = CoachMemory(
        user_id=user_id, role="assistant",
        content=content,
        timestamp=datetime.utcnow() - timedelta(hours=hours_ago),
    )
    db_session.add(msg)
    db_session.commit()
    return msg


def test_qt_insufficient_questions(db_session, test_user):
    """5 soru < 30 esigi -> insufficient_data active, digerleri dormant."""
    for i in range(5):
        _qt_msg(db_session, test_user.id, f"Ne dusunuyorsun bu konuda? Ekstra not {i}.", hours_ago=i+1)

    result = extract_question_typology(db_session, test_user.id)

    assert result["skipped_reason"] is not None
    assert "insufficient_questions" in result["skipped_reason"]

    insuf = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="question_typology",
        title="Yetersiz veri - OARS metrikleri",
    ).first()
    assert insuf is not None
    assert insuf.status == "active"

    dormant = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="question_typology",
        status="dormant",
    ).count()
    assert dormant == 3


def test_qt_low_open_ratio_warning(db_session, test_user):
    """40 closed soru, 5 open -> pct_open=%11 < %40 -> low_open active.
    Reflection 0 -> rq_ratio=0 < 0.5 -> low_rq da active."""
    closed_block = " ".join(["Bu dogru mu?" for _ in range(40)])
    _qt_msg(db_session, test_user.id, closed_block, hours_ago=1)
    open_block = " ".join(["Ne dusunuyorsun?" for _ in range(5)])
    _qt_msg(db_session, test_user.id, open_block, hours_ago=2)

    result = extract_question_typology(db_session, test_user.id)

    assert result["skipped_reason"] is None
    metrics = result["metrics"]
    assert metrics["total_questions"] >= 30
    assert metrics["pct_open"] < QT_PCT_OPEN_THRESHOLD
    assert metrics["rq_ratio"] < QT_RQ_THRESHOLD

    low_open = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Dusuk acik soru orani",
    ).first()
    assert low_open.status == "active"
    assert low_open.sort_priority == QT_WARNING_PRIORITY

    low_rq = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Dusuk reflection-soru orani",
    ).first()
    assert low_rq.status == "active"

    healthy = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="OARS dengesi saglikli",
    ).first()
    assert healthy.status == "dormant"


def test_qt_healthy_oars(db_session, test_user):
    """20 open + 10 closed (pct_open=%66) + 20 reflection (R:Q=0.66)
    -> healthy active, uyari insight'lar dormant."""
    open_block = " ".join(["Ne dusunuyorsun konu hakkinda?" for _ in range(20)])
    _qt_msg(db_session, test_user.id, open_block, hours_ago=1)
    closed_block = " ".join(["Bu yeterli mi?" for _ in range(10)])
    _qt_msg(db_session, test_user.id, closed_block, hours_ago=2)
    refl_block = " ".join(["Anliyorum, sanki kararsizsin." for _ in range(20)])
    _qt_msg(db_session, test_user.id, refl_block, hours_ago=3)

    result = extract_question_typology(db_session, test_user.id)

    assert result["skipped_reason"] is None
    metrics = result["metrics"]
    assert metrics["pct_open"] >= QT_PCT_OPEN_THRESHOLD
    assert metrics["rq_ratio"] >= QT_RQ_THRESHOLD

    healthy = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="OARS dengesi saglikli",
    ).first()
    assert healthy.status == "active"
    assert healthy.sort_priority == QT_HEALTHY_PRIORITY

    low_open = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Dusuk acik soru orani",
    ).first()
    assert low_open.status == "dormant"


def test_qt_state_transition_active_to_dormant(db_session, test_user):
    """1. calistir: low_open active. Sonra veriyi degistir, 2. calistir:
    low_open dormant'a inmeli (full-state UPSERT calistigini kanitlar)."""
    closed_block = " ".join(["Dogru mu?" for _ in range(40)])
    msg1 = _qt_msg(db_session, test_user.id, closed_block, hours_ago=10)

    extract_question_typology(db_session, test_user.id)
    low_open_first = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id, title="Dusuk acik soru orani",
    ).first()
    assert low_open_first.status == "active"

    db_session.delete(msg1)
    db_session.commit()

    open_block = " ".join(["Ne dusunuyorsun?" for _ in range(20)])
    _qt_msg(db_session, test_user.id, open_block, hours_ago=5)
    closed_block2 = " ".join(["Bu mu?" for _ in range(10)])
    _qt_msg(db_session, test_user.id, closed_block2, hours_ago=6)
    refl_block = " ".join(["Anliyorum, demek ki kararsizsin." for _ in range(20)])
    _qt_msg(db_session, test_user.id, refl_block, hours_ago=7)

    extract_question_typology(db_session, test_user.id)
    db_session.refresh(low_open_first)
    assert low_open_first.status == "dormant"  # KRITIK: full-state UPSERT

    healthy = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id, title="OARS dengesi saglikli",
    ).first()
    assert healthy.status == "active"


def test_qt_idempotent_rerun(db_session, test_user):
    """Ayni veri 2 kez -> created sayisi 0, insight sayisi 4 sabit."""
    open_block = " ".join(["Ne dusunuyorsun?" for _ in range(20)])
    _qt_msg(db_session, test_user.id, open_block, hours_ago=1)
    closed_block = " ".join(["Mi?" for _ in range(10)])
    _qt_msg(db_session, test_user.id, closed_block, hours_ago=2)
    refl_block = " ".join(["Anliyorum sanki." for _ in range(20)])
    _qt_msg(db_session, test_user.id, refl_block, hours_ago=3)

    result1 = extract_question_typology(db_session, test_user.id)
    count1 = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id, insight_type="question_typology",
    ).count()

    result2 = extract_question_typology(db_session, test_user.id)
    count2 = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id, insight_type="question_typology",
    ).count()

    assert count1 == count2 == 4
    assert result2["created"] == 0
    assert result2["updated"] == 4


# ============================================================
# TESTS: category_account_preference
# ============================================================

def _make_account(db_session, user_id, name, account_type="cash"):
    """Test fixture: hesap olustur."""
    from app.models import AccountType
    acct = Account(
        user_id=user_id,
        name=name,
        account_type=AccountType(account_type) if isinstance(account_type, str) else account_type,
        balance=0.0,
    )
    db_session.add(acct)
    db_session.commit()
    return acct


def _make_expense(db_session, user_id, account_id, category, amount=50.0, days_ago=1):
    """Test fixture: expense transaction."""
    tx = Transaction(
        user_id=user_id,
        account_id=account_id,
        transaction_type=TransactionType.expense,
        amount=amount,
        category=category,
        transaction_date=(datetime.utcnow() - timedelta(days=days_ago)).date(),
        description=f"test {category}",
    )
    db_session.add(tx)
    db_session.commit()
    return tx


def test_cap_insufficient_transactions(db_session, test_user):
    """3 islem < 5 esigi -> hicbir insight uretilmemeli."""
    acct = _make_account(db_session, test_user.id, "Nakit", "cash")
    for i in range(3):
        _make_expense(db_session, test_user.id, acct.id, "yiyecek", days_ago=i+1)

    result = extract_category_account_preference(db_session, test_user.id)

    assert result["dominant_count"] == 0
    assert result["created"] == 0

    insights = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="category_account_preference",
    ).all()
    assert len(insights) == 0


def test_cap_dominant_pattern_active(db_session, test_user):
    """yiyecek kategorisinde 8/10 (%80) Garanti Kart -> active insight."""
    cash = _make_account(db_session, test_user.id, "Nakit Kasa", "cash")
    card = _make_account(db_session, test_user.id, "Garanti Kart", "credit_card")

    for i in range(8):
        _make_expense(db_session, test_user.id, card.id, "yiyecek", days_ago=i+1)
    for i in range(2):
        _make_expense(db_session, test_user.id, cash.id, "yiyecek", days_ago=10+i)

    result = extract_category_account_preference(db_session, test_user.id)

    assert result["created"] == 1
    assert result["dominant_count"] == 1

    insight = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Kategori tercihi: yiyecek",
    ).first()
    assert insight is not None
    assert insight.status == "active"
    assert insight.evidence_count == 8
    assert insight.sort_priority == CAP_DOMINANT_PRIORITY
    assert insight.confidence_basis == "data_grounded"
    assert "Garanti Kart" in insight.content
    assert "80%" in insight.content


def test_cap_no_dominant_below_threshold(db_session, test_user):
    """6/10 (%60) - %70 esiginin altinda -> insight YOK."""
    cash = _make_account(db_session, test_user.id, "Nakit", "cash")
    card = _make_account(db_session, test_user.id, "Kart", "credit_card")

    for i in range(6):
        _make_expense(db_session, test_user.id, card.id, "ulasim", days_ago=i+1)
    for i in range(4):
        _make_expense(db_session, test_user.id, cash.id, "ulasim", days_ago=7+i)

    result = extract_category_account_preference(db_session, test_user.id)

    assert result["dominant_count"] == 0

    insights = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="category_account_preference",
    ).all()
    assert len(insights) == 0


def test_cap_multiple_categories_dormant_sweep(db_session, test_user):
    """1. cagri: yiyecek + ulasim dominant (2 active insight).
    2. cagri: ulasim'da yeni hesap dominant olur, yiyecek dominant kaybeder.
    Eski yiyecek insight 'dormant' olmali (full-state sweep)."""
    cash = _make_account(db_session, test_user.id, "Nakit", "cash")
    card1 = _make_account(db_session, test_user.id, "Kart1", "credit_card")
    card2 = _make_account(db_session, test_user.id, "Kart2", "credit_card")

    # Asama 1: yiyecek -> Kart1 dominant (8/10), ulasim -> Nakit dominant (7/8)
    for i in range(8):
        _make_expense(db_session, test_user.id, card1.id, "yiyecek", days_ago=i+1)
    for i in range(2):
        _make_expense(db_session, test_user.id, cash.id, "yiyecek", days_ago=10+i)
    for i in range(7):
        _make_expense(db_session, test_user.id, cash.id, "ulasim", days_ago=i+1)
    _make_expense(db_session, test_user.id, card1.id, "ulasim", days_ago=15)

    result1 = extract_category_account_preference(db_session, test_user.id)
    assert result1["dominant_count"] == 2
    assert result1["created"] == 2

    yiyecek_first = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id, title="Kategori tercihi: yiyecek",
    ).first()
    assert yiyecek_first.status == "active"

    # Asama 2: yiyecek'e cok Nakit ekle (Kart1 artik dominant degil)
    for i in range(10):
        _make_expense(db_session, test_user.id, cash.id, "yiyecek", days_ago=20+i)

    result2 = extract_category_account_preference(db_session, test_user.id)

    db_session.refresh(yiyecek_first)
    assert yiyecek_first.status == "dormant", \
        f"yiyecek dormant olmaliydi ama {yiyecek_first.status}"
    assert result2["dormant_swept"] >= 1


def test_cap_idempotent_rerun(db_session, test_user):
    """Ayni veri 2 kez -> insight sayisi sabit, created=0."""
    card = _make_account(db_session, test_user.id, "Kart", "credit_card")
    cash = _make_account(db_session, test_user.id, "Nakit", "cash")
    for i in range(8):
        _make_expense(db_session, test_user.id, card.id, "yiyecek", days_ago=i+1)
    for i in range(2):
        _make_expense(db_session, test_user.id, cash.id, "yiyecek", days_ago=10+i)

    result1 = extract_category_account_preference(db_session, test_user.id)
    count1 = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id, insight_type="category_account_preference",
    ).count()

    result2 = extract_category_account_preference(db_session, test_user.id)
    count2 = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id, insight_type="category_account_preference",
    ).count()

    assert count1 == count2 == 1
    assert result2["created"] == 0
    assert result2["updated"] == 1
    assert result2["dormant_swept"] == 0


# ============================================================
# TESTS: action_rejection_pattern
# ============================================================

def _make_pending(db_session, user_id, action_type, status, days_ago=1):
    """Test fixture: PendingAction satiri olustur."""
    pa = PendingAction(
        user_id=user_id,
        action_type=action_type,
        payload="{}",
        summary=f"test {action_type}",
        status=status,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
        resolved_at=(
            datetime.utcnow() - timedelta(days=days_ago)
            if status != ActionStatus.pending else None
        ),
    )
    db_session.add(pa)
    db_session.commit()
    return pa


def test_arp_insufficient_sample(db_session, test_user):
    """3 resolved < 5 esigi -> hicbir insight uretilmemeli."""
    for i in range(2):
        _make_pending(db_session, test_user.id, "add_transaction",
                      ActionStatus.rejected, days_ago=i+1)
    _make_pending(db_session, test_user.id, "add_transaction",
                  ActionStatus.executed, days_ago=3)

    result = extract_action_rejection_pattern(db_session, test_user.id)

    assert result["active_count"] == 0
    assert result["created"] == 0

    insights = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="action_rejection_pattern",
    ).all()
    assert len(insights) == 0


def test_arp_dominant_rejection_active(db_session, test_user):
    """add_transaction icin 7 rejected / 3 executed = %70 -> active insight."""
    for i in range(7):
        _make_pending(db_session, test_user.id, "add_transaction",
                      ActionStatus.rejected, days_ago=i+1)
    for i in range(3):
        _make_pending(db_session, test_user.id, "add_transaction",
                      ActionStatus.executed, days_ago=10+i)

    result = extract_action_rejection_pattern(db_session, test_user.id)

    assert result["created"] == 1
    assert result["active_count"] == 1

    insight = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Aksiyon ret pateni: add_transaction",
    ).first()
    assert insight is not None
    assert insight.status == "active"
    assert insight.evidence_count == 7
    assert insight.sort_priority == ARP_DOMINANT_PRIORITY
    assert insight.confidence_basis == "data_grounded"
    assert "70%" in insight.content


def test_arp_below_threshold_no_insight(db_session, test_user):
    """4 rejected / 6 executed = %40 -> %50 esigin altinda, insight YOK."""
    for i in range(4):
        _make_pending(db_session, test_user.id, "update_balance",
                      ActionStatus.rejected, days_ago=i+1)
    for i in range(6):
        _make_pending(db_session, test_user.id, "update_balance",
                      ActionStatus.executed, days_ago=5+i)

    result = extract_action_rejection_pattern(db_session, test_user.id)

    assert result["active_count"] == 0

    insights = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        insight_type="action_rejection_pattern",
    ).all()
    assert len(insights) == 0


def test_arp_pending_excluded_from_calculation(db_session, test_user):
    """Pending statulu kayitlar ne payda ne paya dahil olmamali.
    Test: 5 rejected + 2 executed (=%71 ret) + 50 pending varsa,
    pending'leri saymadan rate dogru hesaplanmali."""
    for i in range(5):
        _make_pending(db_session, test_user.id, "add_transaction",
                      ActionStatus.rejected, days_ago=i+1)
    for i in range(2):
        _make_pending(db_session, test_user.id, "add_transaction",
                      ActionStatus.executed, days_ago=6+i)
    for i in range(50):
        _make_pending(db_session, test_user.id, "add_transaction",
                      ActionStatus.pending, days_ago=8+i)

    result = extract_action_rejection_pattern(db_session, test_user.id)

    assert result["active_count"] == 1

    insight = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Aksiyon ret pateni: add_transaction",
    ).first()
    refs = json.loads(insight.source_refs)
    assert refs["total_resolved"] == 7
    assert refs["rejected_count"] == 5
    assert refs["executed_count"] == 2


def test_arp_dormant_sweep_on_behavior_change(db_session, test_user):
    """1. cagri: add_transaction reddediliyor (%80) -> active.
    2. cagri: kullanici kabul etmeye basladi -> dormant'a dusmeli."""
    for i in range(8):
        _make_pending(db_session, test_user.id, "add_transaction",
                      ActionStatus.rejected, days_ago=20+i)
    for i in range(2):
        _make_pending(db_session, test_user.id, "add_transaction",
                      ActionStatus.executed, days_ago=30+i)

    extract_action_rejection_pattern(db_session, test_user.id)
    insight_first = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Aksiyon ret pateni: add_transaction",
    ).first()
    assert insight_first.status == "active"

    # 15 yeni executed: 8 rejected / 17 executed = %32 -> esigin alti
    for i in range(15):
        _make_pending(db_session, test_user.id, "add_transaction",
                      ActionStatus.executed, days_ago=i+1)

    result2 = extract_action_rejection_pattern(db_session, test_user.id)

    db_session.refresh(insight_first)
    assert insight_first.status == "dormant", \
        f"Beklenen dormant, gercek {insight_first.status}"
    assert result2["dormant_swept"] >= 1


# ============================================================
# TESTS: breakthrough
# ============================================================

def _make_snapshot(db_session, user_id, days_ago, net_worth_full=0.0,
                   card_debt=0.0, loan_debt=0.0, investment_value=0.0,
                   cash=0.0, net_worth_seen=None, receivables=0.0):
    """Test fixture: NetWorthSnapshot satiri."""
    snap = NetWorthSnapshot(
        user_id=user_id,
        snapshot_date=(datetime.utcnow() - timedelta(days=days_ago)).date(),
        net_worth_full=net_worth_full,
        net_worth_seen=net_worth_seen if net_worth_seen is not None else net_worth_full,
        cash=cash,
        card_debt=card_debt,
        loan_debt=loan_debt,
        investment_value=investment_value,
        receivables=receivables,
    )
    db_session.add(snap)
    db_session.commit()
    return snap


def test_bt_insufficient_snapshots(db_session, test_user):
    """10 snapshot var, esik 20+60 -> insufficient."""
    for i in range(10):
        _make_snapshot(db_session, test_user.id, days_ago=i, net_worth_full=1000)

    result = extract_breakthrough(db_session, test_user.id)

    assert result["skipped_reason"] is not None
    assert "insufficient_snapshots" in result["skipped_reason"]
    assert result["active_count"] == 0


def test_bt_net_worth_improvement_active(db_session, test_user):
    """30 gun ort -10K, onceki 90 gun ort -20K -> +10K iyilesme -> active."""
    for i in range(30):
        _make_snapshot(db_session, test_user.id, days_ago=i, net_worth_full=-10000.0)
    for i in range(30, 120):
        _make_snapshot(db_session, test_user.id, days_ago=i, net_worth_full=-20000.0)

    result = extract_breakthrough(db_session, test_user.id)

    assert result["skipped_reason"] is None
    assert result["active_count"] >= 1

    insight = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Kutlanacak ilerleme: Net deger iyilesmesi",
    ).first()
    assert insight is not None
    assert insight.status == "active"
    assert insight.sort_priority == BT_DOMINANT_PRIORITY
    assert insight.confidence_basis == "data_grounded"


def test_bt_below_threshold_no_insight(db_session, test_user):
    """+1000 TL iyilesme - 5000 esiginin altinda -> insight YOK."""
    for i in range(30):
        _make_snapshot(db_session, test_user.id, days_ago=i, net_worth_full=-19000.0)
    for i in range(30, 120):
        _make_snapshot(db_session, test_user.id, days_ago=i, net_worth_full=-20000.0)

    result = extract_breakthrough(db_session, test_user.id)

    assert result["skipped_reason"] is None

    nw_insight = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Kutlanacak ilerleme: Net deger iyilesmesi",
    ).first()
    assert nw_insight is None


def test_bt_multi_component_breakthroughs(db_session, test_user):
    """Hem kart borcu azaldi hem yatirim buyudu -> 2+ ayri active insight."""
    for i in range(30):
        _make_snapshot(db_session, test_user.id, days_ago=i,
                       card_debt=2000.0, investment_value=20000.0,
                       net_worth_full=18000.0)
    for i in range(30, 120):
        _make_snapshot(db_session, test_user.id, days_ago=i,
                       card_debt=8000.0, investment_value=15000.0,
                       net_worth_full=7000.0)

    result = extract_breakthrough(db_session, test_user.id)

    assert result["active_count"] >= 2

    card = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Kutlanacak ilerleme: Kart borcu azalmasi",
    ).first()
    assert card.status == "active"

    inv = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Kutlanacak ilerleme: Yatirim buyumesi",
    ).first()
    assert inv.status == "active"


def test_bt_dormant_sweep_on_regression(db_session, test_user):
    """1. cagri: yatirim buyumesi var. 2. cagri: yatirim tersine dondu -> dormant."""
    for i in range(30):
        _make_snapshot(db_session, test_user.id, days_ago=i, investment_value=20000.0)
    for i in range(30, 120):
        _make_snapshot(db_session, test_user.id, days_ago=i, investment_value=15000.0)

    extract_breakthrough(db_session, test_user.id)
    inv_first = db_session.query(CoachInsight).filter_by(
        user_id=test_user.id,
        title="Kutlanacak ilerleme: Yatirim buyumesi",
    ).first()
    assert inv_first is not None
    assert inv_first.status == "active"

    # Recent snapshot'lari sil, baseline ile ayni degere dondur
    db_session.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.user_id == test_user.id,
        NetWorthSnapshot.snapshot_date >= (datetime.utcnow() - timedelta(days=30)).date(),
    ).delete(synchronize_session=False)
    db_session.commit()
    for i in range(30):
        _make_snapshot(db_session, test_user.id, days_ago=i, investment_value=15000.0)

    result2 = extract_breakthrough(db_session, test_user.id)

    db_session.refresh(inv_first)
    assert inv_first.status == "dormant"
    assert result2["dormant_swept"] >= 1

