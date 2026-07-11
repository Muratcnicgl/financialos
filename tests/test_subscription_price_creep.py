"""
FEAT-007 — abonelik fiyat artışı (price creep) uyarısı.
_subscription_price_alerts: bir aboneliğin tutarı sessizce arttıysa cockpit alert'i (uyarı).
Yalnızca ARTIŞ uyarılır (düşüş değil). Deterministik izole DB.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Transaction, TransactionType
from app.rules_engine import _subscription_price_alerts, generate_cockpit

TODAY = date(2026, 6, 1)


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


def _series(db, desc, amounts):
    """len(amounts) kadar ~30 gün arayla işlem (en eski → en yeni)."""
    n = len(amounts)
    for i, amt in enumerate(amounts):
        db.add(Transaction(user_id=1, transaction_type=TransactionType.expense,
                           amount=amt, category="abonelik", description=desc,
                           transaction_date=TODAY - timedelta(days=(n - 1 - i) * 30 + 1)))
    db.commit()


def test_zam_uyarisi_uretir(db):
    _series(db, "Spotify", [59.99, 59.99, 74.99, 74.99])   # zam
    alerts = _subscription_price_alerts(1, TODAY, db)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["seviye"] == "uyari"
    assert "Spotify" in a["baslik"]
    assert "74.99" in a["mesaj"]      # rules_engine alert konvansiyonu: {:,.2f} (nokta ondalık, #120 ile tutarlı)
    assert a["tutar"] == 74.99


def test_sabit_fiyat_uyari_yok(db):
    _series(db, "Netflix", [59.99, 59.99, 59.99])          # sabit
    assert _subscription_price_alerts(1, TODAY, db) == []


def test_fiyat_dususu_uyari_yok(db):
    _series(db, "Gym", [200.0, 200.0, 150.0])              # indirim → uyarı yok
    assert _subscription_price_alerts(1, TODAY, db) == []


def test_zam_cockpit_alerts_e_dusuyor(db):
    _series(db, "Spotify", [49.99, 49.99, 64.99])
    cockpit = generate_cockpit(1, TODAY, db)
    zam = [a for a in cockpit["alerts"] if a.get("baslik", "").startswith("Abonelik zammı")]
    assert len(zam) == 1
    assert zam[0]["seviye"] == "uyari"
