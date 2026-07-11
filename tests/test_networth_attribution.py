"""
FEAT-021 — net değer değişim ayrıştırması (calculate_networth_attribution).
Snapshot'lardan objektif: sürücüler (nakit/kart-ödeme/kredi-ödeme/yatırım/alacak) toplamı = değişim.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, NetWorthSnapshot
from app.rules_engine import calculate_networth_attribution

TODAY = date(2026, 5, 15)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


def _snap(db, d, cash, card, loan, inv, rec):
    net_full = cash + inv + rec - card - loan
    db.add(NetWorthSnapshot(user_id=1, snapshot_date=d, net_worth_seen=cash + inv - card - loan,
                            net_worth_full=net_full, cash=cash, card_debt=card, loan_debt=loan,
                            investment_value=inv, receivables=rec))
    db.commit()


def test_yetersiz_gecmis_none(db):
    assert calculate_networth_attribution(1, TODAY, db) is None       # hiç snapshot yok
    _snap(db, date(2026, 5, 10), 1000, 12000, 30000, 5000, 8000)
    # ay başı (<= May 1) referansı yok → None
    assert calculate_networth_attribution(1, TODAY, db) is None


def test_ayristirma_surucureler(db):
    _snap(db, date(2026, 5, 1), 1000, 12000, 30000, 5000, 8000)   # ref net_full = -28000
    _snap(db, date(2026, 5, 15), 800, 11000, 25000, 5500, 8000)   # latest net_full = -21700
    r = calculate_networth_attribution(1, TODAY, db)
    assert r is not None
    assert r["degisim"] == 6300.0
    assert r["baslangic_net"] == -28000.0 and r["guncel_net"] == -21700.0
    # sürücüler toplamı = değişim
    assert round(sum(s["katki"] for s in r["surucureler"]), 2) == 6300.0
    # en etkili sürücü: kredi ödeme (5000)
    assert r["surucureler"][0]["ad"] == "Kredi ödeme"
    assert r["surucureler"][0]["katki"] == 5000.0


def test_endpoint_available_false():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_db, get_current_user
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="m")); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        r = TestClient(app).get("/api/reports/net-worth-attribution")
        assert r.status_code == 200 and r.json()["available"] is False
    finally:
        app.dependency_overrides.clear(); s.close()
