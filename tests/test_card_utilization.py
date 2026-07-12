"""
FEAT-016 — kredi kartı kullanım oranı (utilization) + trend + kredi-sağlık bandı.

calculate_card_utilization: toplam kart borcu / toplam limit, band sınıflaması,
%30 sağlıklı borç hedefi ve (≥7 gün geçmiş varsa) NetWorthSnapshot'tan iyileşme trendi.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, NetWorthSnapshot
from app.rules_engine import calculate_card_utilization


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


def _card(db, balance, limit):
    db.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card,
                   balance=balance, credit_limit=limit))
    db.commit()


def test_kart_yoksa_none(db):
    assert calculate_card_utilization(1, date(2026, 7, 12), db) is None


def test_limit_sifir_none(db):
    _card(db, 500, 0)
    assert calculate_card_utilization(1, date(2026, 7, 12), db) is None


def test_kritik_band_ve_hedef(db):
    _card(db, 99800, 100000)  # %99.8 — Murat senaryosu
    r = calculate_card_utilization(1, date(2026, 7, 12), db)
    assert r["oran"] == 99.8
    assert r["band"] == "kritik"
    # %30'a inmek için borç 30000 olmalı
    assert r["saglikli_borc_hedefi"] == 30000.0
    assert r["kalan_limit"] == 200.0
    assert r["kart_adet"] == 1
    assert "kredi notunu" in r["mesaj"].lower() or "kredi not" in r["mesaj"].lower()


def test_saglikli_band(db):
    _card(db, 1500, 10000)  # %15
    r = calculate_card_utilization(1, date(2026, 7, 12), db)
    assert r["oran"] == 15.0
    assert r["band"] == "saglikli"


def test_bant_esikleri(db):
    _card(db, 3000, 10000)  # %30 tam → orta (>= _UTIL_HEALTHY)
    r = calculate_card_utilization(1, date(2026, 7, 12), db)
    assert r["band"] == "orta"


def test_coklu_kart_toplanir(db):
    _card(db, 8000, 10000)
    _card(db, 2000, 10000)
    r = calculate_card_utilization(1, date(2026, 7, 12), db)
    assert r["toplam_borc"] == 10000.0
    assert r["toplam_limit"] == 20000.0
    assert r["oran"] == 50.0
    assert r["kart_adet"] == 2


def test_trend_iyilesme(db):
    today = date(2026, 7, 12)
    _card(db, 90000, 100000)  # bugün %90
    # 30 gün önce kart borcu 98000 → o günkü oran (bugünkü limitle) %98 → iyileşme
    db.add(NetWorthSnapshot(user_id=1, snapshot_date=today - timedelta(days=30),
                            net_worth_seen=0, net_worth_full=0, cash=0,
                            card_debt=98000, loan_debt=0, investment_value=0, receivables=0))
    db.commit()
    r = calculate_card_utilization(1, today, db)
    assert r["trend"] is not None
    assert r["trend"]["baslangic_oran"] == 98.0
    assert r["trend"]["degisim"] == -8.0     # 90 - 98
    assert r["trend"]["iyilesme"] is True


def test_trend_yetersiz_gecmis_none(db):
    today = date(2026, 7, 12)
    _card(db, 90000, 100000)
    # sadece 3 gün önce → <7 gün → trend None
    db.add(NetWorthSnapshot(user_id=1, snapshot_date=today - timedelta(days=3),
                            net_worth_seen=0, net_worth_full=0, cash=0,
                            card_debt=98000, loan_debt=0, investment_value=0, receivables=0))
    db.commit()
    r = calculate_card_utilization(1, today, db)
    assert r["trend"] is None


def test_trend_kotulesme(db):
    today = date(2026, 7, 12)
    _card(db, 95000, 100000)  # bugün %95
    db.add(NetWorthSnapshot(user_id=1, snapshot_date=today - timedelta(days=20),
                            net_worth_seen=0, net_worth_full=0, cash=0,
                            card_debt=90000, loan_debt=0, investment_value=0, receivables=0))
    db.commit()
    r = calculate_card_utilization(1, today, db)
    assert r["trend"]["degisim"] == 5.0
    assert r["trend"]["iyilesme"] is False


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
