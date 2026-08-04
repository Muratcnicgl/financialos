"""M27 — app/startup.py catch_up_snapshots dal kapsamı (0% → yüksek)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.startup as startup
from app.models import Base, User, NetWorthSnapshot


def _snap(uid, d):
    return NetWorthSnapshot(user_id=uid, snapshot_date=d, net_worth_seen=0, net_worth_full=0,
                            cash=0, card_debt=0, loan_debt=0, investment_value=0, receivables=0)


@pytest.fixture
def Session(monkeypatch):
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    SessionLocal = sessionmaker(bind=eng)
    monkeypatch.setattr(startup, "SessionLocal", SessionLocal)
    return SessionLocal


def test_kullanici_yok_atlar(Session):
    startup.catch_up_snapshots()  # user yok → sessizce döner (patlamaz)


def test_snapshot_yok_atlar(Session):
    s = Session()
    s.add(User(id=1, name="m"))
    s.commit(); s.close()
    startup.catch_up_snapshots()  # snapshot yok → manuel backfill notu, döner


def test_snapshot_guncel_atlar(Session):
    s = Session()
    s.add(User(id=1, name="m"))
    s.add(_snap(1, date.today()))
    s.commit(); s.close()
    startup.catch_up_snapshots()  # güncel → atlar


def test_eksik_gun_backfill_cagirir(Session, monkeypatch):
    s = Session()
    s.add(User(id=1, name="m"))
    s.add(_snap(1, date.today() - timedelta(days=5)))
    s.commit(); s.close()
    called = {}
    # BUG #163: catch-up artık kullanıcı başına çağırır → imza `user_id` de alır
    monkeypatch.setattr(
        "scripts.backfill_net_worth.run_backfill",
        lambda start, end, verbose=False, user_id=None:
            called.setdefault("n", (start, end, user_id)) or 5)
    startup.catch_up_snapshots()
    assert "n" in called  # backfill tetiklendi (eksik günler için)
    assert called["n"][2] == 1  # BUG #163: hedef kullanıcı açıkça geçirilir
