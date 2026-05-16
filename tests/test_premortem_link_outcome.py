"""
Unit tests for link_premortem_outcome helper — app/premortem.py.
Router'a girmeden dogrudan helper'i test eder.
StaticPool ile :memory: SQLite tek baglanti garanti edilir.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, DecisionJournal, User
from app.premortem import link_premortem_outcome


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session: Session) -> User:
    u = User(name="link_outcome_test_user")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _make_dj(db: Session, user_id: int, pending_id: int) -> DecisionJournal:
    dj = DecisionJournal(
        user_id=user_id,
        decision_text=f"PendingAction#{pending_id}",
        decision_type="add_transaction",
        predicted_outcome="Bakiye artacak",
        mc_rules_applied=json.dumps([]),
        cockpit_snapshot_hash="abc123",
        premortem_scenarios=json.dumps([
            {
                "id": "S1", "title": "Test senaryo 1", "probability_label": "orta",
                "impact_tl": -500.0,
                "narrative": "Bu aksiyon basarisiz oldu cunku test senaryosu yazildi.",
                "mitigation": "Test mitigation aksiyonu.",
            }
        ]),
    )
    db.add(dj)
    db.commit()
    db.refresh(dj)
    return dj


# ============================================================
# TESTLER
# ============================================================

def test_link_outcome_basarili_aksiyon(db_session, test_user):
    """Basarili execute: related_action_id, actual_outcome, score=1 yazilir."""
    dj = _make_dj(db_session, test_user.id, pending_id=42)

    result = link_premortem_outcome(
        session=db_session,
        pending_action_id=42,
        action_history_id=99,
        success=True,
        message="Bakiye guncellendi: 5000 TL",
        net_worth_delta=100.0,
    )

    assert result is not None
    assert result.related_action_id == 99
    assert result.actual_outcome == "Bakiye guncellendi: 5000 TL"
    assert result.outcome_evaluated_at is not None
    assert result.outcome_score == 1

    # DB'den de dogrula
    refreshed = db_session.execute(
        select(DecisionJournal).where(DecisionJournal.id == dj.id)
    ).scalar_one()
    assert refreshed.related_action_id == 99
    assert refreshed.outcome_score == 1


def test_link_outcome_basarisiz_aksiyon(db_session, test_user):
    """Basarisiz execute: outcome_score=-1, mesaj yazilir."""
    _make_dj(db_session, test_user.id, pending_id=55)

    result = link_premortem_outcome(
        session=db_session,
        pending_action_id=55,
        action_history_id=77,
        success=False,
        message="Hata: yetersiz bakiye",
        net_worth_delta=-200.0,
    )

    assert result is not None
    assert result.outcome_score == -1
    assert result.actual_outcome == "Hata: yetersiz bakiye"
    assert result.related_action_id == 77


def test_link_outcome_premortem_cagirilmamis_aksiyon(db_session, test_user):
    """Premortem hic cagirilmamis aksiyon icin None doner, DB'de DJ yok."""
    # DJ olusturma — pending_id=99 icin hicbir premortem kaydi yok

    result = link_premortem_outcome(
        session=db_session,
        pending_action_id=99,
        action_history_id=1,
        success=True,
        message="OK",
    )

    assert result is None

    # DB'de hicbir DJ kaydi olmamali
    all_djs = db_session.execute(select(DecisionJournal)).scalars().all()
    assert all_djs == []
