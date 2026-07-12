"""
FEAT-024 — enflasyon-düzeltilmiş (reel) net değer (calculate_real_networth).
Nominal vs reel değişim; Türkiye'de enflasyon serveti erir, borcu eritir. Deterministik
(annual_inflation açıkça verilir, 365 gün → temiz faktör).
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, NetWorthSnapshot
from app.rules_engine import calculate_real_networth

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


def _snap(db, d, net_full):
    db.add(NetWorthSnapshot(user_id=1, snapshot_date=d, net_worth_seen=net_full,
                            net_worth_full=net_full, cash=0, card_debt=0, loan_debt=0,
                            investment_value=0, receivables=0))
    db.commit()


def test_yetersiz_gecmis_none(db):
    assert calculate_real_networth(1, TODAY, db) is None
    _snap(db, date(2026, 5, 1), 100000)
    assert calculate_real_networth(1, TODAY, db) is None   # tek snapshot


def test_pozitif_servet_enflasyon_erir(db):
    # 1 yıl (365 gün), nominal DEĞİŞMEDİ (100k→100k), %40 enflasyon → reel 100k/1.4 ≈ 71.4k
    _snap(db, date(2025, 5, 15), 100000)
    _snap(db, date(2026, 5, 15), 100000)
    r = calculate_real_networth(1, TODAY, db, annual_inflation=0.40)
    assert r["gun"] == 365
    assert r["nominal_degisim"] == 0.0
    assert abs(r["reel_net"] - 71428.57) < 1
    assert abs(r["reel_degisim"] - (-28571.43)) < 1     # reel fakirleşme
    assert r["enflasyon_etkisi"] < 0                     # enflasyon aşındırdı


def test_borclu_enflasyon_borcu_eritir(db):
    # borçlu: net -100k, 1 yıl, nominal aynı → reel -100k/1.4 ≈ -71.4k → borç REEL hafifledi
    _snap(db, date(2025, 5, 15), -100000)
    _snap(db, date(2026, 5, 15), -100000)
    r = calculate_real_networth(1, TODAY, db, annual_inflation=0.40)
    assert r["reel_degisim"] > 0                         # borç eridi (reel iyileşme)
    assert r["enflasyon_etkisi"] > 0


def test_endpoint():
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
        r = TestClient(app).get("/api/reports/real-net-worth")
        assert r.status_code == 200 and r.json()["available"] is False
    finally:
        app.dependency_overrides.clear(); s.close()
