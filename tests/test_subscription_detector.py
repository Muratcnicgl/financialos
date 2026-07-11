"""
FEAT-006 — abonelik denetçisi (detect_subscriptions).
İşlem geçmişinde tekrarlayan abonelik-benzeri ödemeleri tespit eder (Rocket Money/Monarch ilhamı).
Ayırt edici: düzenli aralık (aylık/yıllık) + farklı-tutar ≤ 2 → değişken harcama elenir.
Deterministik izole DB.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Transaction, TransactionType
from app.rules_engine import detect_subscriptions

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


def _exp(db, desc, amount, when):
    db.add(Transaction(user_id=1, transaction_type=TransactionType.expense,
                       amount=amount, category="abonelik", description=desc,
                       transaction_date=when))
    db.commit()


def _monthly_series(db, desc, amount, n=4, start_offset=120):
    """n ay boyunca ~30 gün arayla aynı tutar."""
    for i in range(n):
        _exp(db, desc, amount, TODAY - timedelta(days=start_offset - i * 30))


def _sub_by_key(res, key):
    return next((s for s in res["abonelikler"] if s["anahtar"] == key), None)


def test_aylik_abonelik_tespit(db):
    _monthly_series(db, "Netflix", 59.99, n=4)
    res = detect_subscriptions(1, TODAY, db)
    s = _sub_by_key(res, "netflix")
    assert s is not None
    assert s["period"] == "monthly"
    assert s["aylik_maliyet"] == 59.99
    assert s["tekrar"] == 4
    assert s["fiyat_degisti"] is False


def test_degisken_harcama_elenir(db):
    # "market" 4 kez ama hep farklı tutar → abonelik DEĞİL
    for i, amt in enumerate([230.0, 415.5, 88.0, 302.25]):
        _exp(db, "Market", amt, TODAY - timedelta(days=120 - i * 30))
    res = detect_subscriptions(1, TODAY, db)
    assert _sub_by_key(res, "market") is None


def test_az_tekrar_elenir(db):
    _monthly_series(db, "Spotify", 49.99, n=2)   # < 3
    res = detect_subscriptions(1, TODAY, db)
    assert _sub_by_key(res, "spotify") is None


def test_duzensiz_aralik_elenir(db):
    # aynı tutar ama düzensiz aralık (5, 90, 12 gün) → abonelik değil
    _exp(db, "Rastgele", 30.0, TODAY - timedelta(days=120))
    _exp(db, "Rastgele", 30.0, TODAY - timedelta(days=115))
    _exp(db, "Rastgele", 30.0, TODAY - timedelta(days=25))
    _exp(db, "Rastgele", 30.0, TODAY - timedelta(days=13))
    res = detect_subscriptions(1, TODAY, db)
    assert _sub_by_key(res, "rastgele") is None


def test_fiyat_artisi_yine_tespit_ve_bayrak(db):
    # 59.99 ×2 sonra 74.99 ×2 → 2 farklı tutar → abonelik + fiyat_degisti=True
    for i, amt in enumerate([59.99, 59.99, 74.99, 74.99]):
        _exp(db, "Spotify", amt, TODAY - timedelta(days=120 - i * 30))
    res = detect_subscriptions(1, TODAY, db)
    s = _sub_by_key(res, "spotify")
    assert s is not None
    assert s["fiyat_degisti"] is True
    assert s["guncel_tutar"] == 74.99      # en son tutar


def test_yillik_abonelik_aylik_maliyet(db):
    # ~365 gün arayla 3 kez → yıllık; aylik_maliyet = tutar/12
    for i in range(3):
        _exp(db, "Amazon Prime", 600.0, TODAY - timedelta(days=730 - i * 365))
    res = detect_subscriptions(1, TODAY, db, lookback_days=800)
    s = _sub_by_key(res, "amazon prime")
    assert s is not None
    assert s["period"] == "annual"
    assert s["aylik_maliyet"] == 50.0      # 600/12


def test_recurring_ay_soneki_birlesir(db):
    # RecurringExpense tetikleyici "Netflix — Mayıs 2026" formatı → aynı gruba düşer
    _exp(db, "Netflix — Mart 2026", 59.99, TODAY - timedelta(days=90))
    _exp(db, "Netflix — Nisan 2026", 59.99, TODAY - timedelta(days=60))
    _exp(db, "Netflix — Mayıs 2026", 59.99, TODAY - timedelta(days=30))
    res = detect_subscriptions(1, TODAY, db)
    s = _sub_by_key(res, "netflix")
    assert s is not None and s["tekrar"] == 3


def test_ozet_toplamlar(db):
    _monthly_series(db, "Netflix", 59.99, n=3)
    _monthly_series(db, "Spotify", 49.99, n=3)
    res = detect_subscriptions(1, TODAY, db)
    assert res["adet"] == 2
    assert res["aylik_toplam"] == round(59.99 + 49.99, 2)
    assert res["yillik_toplam"] == round((59.99 + 49.99) * 12, 2)
    # en pahalı önce
    assert res["abonelikler"][0]["anahtar"] == "netflix"


# ============================================================
# HTTP endpoint — GET /api/subscriptions
# ============================================================

def test_cockpit_abonelik_yuku(db):
    """FEAT-006: generate_cockpit toplam abonelik yükünü (aylık/yıllık/adet) sunar."""
    from app.rules_engine import generate_cockpit
    from app.models import Account, AccountType
    _monthly_series(db, "Netflix", 59.99, n=3)
    _monthly_series(db, "Spotify", 49.99, n=3)
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=1000.0))
    db.commit()
    cockpit = generate_cockpit(1, TODAY, db)
    yuku = cockpit["abonelik_yuku"]
    assert yuku["adet"] == 2
    assert yuku["aylik"] == round(59.99 + 49.99, 2)
    assert yuku["yillik"] == round((59.99 + 49.99) * 12, 2)


def test_subscriptions_endpoint():
    """Endpoint 200 + tespit edilen abonelik + özet döner (bugüne göreli tarihler)."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_db, get_current_user

    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    # endpoint date.today() kullanır → tarihleri gerçek bugüne göre kur
    real_today = date.today()
    for i in range(4):
        s.add(Transaction(user_id=1, transaction_type=TransactionType.expense,
                          amount=59.99, category="abonelik", description="Netflix",
                          transaction_date=real_today - timedelta(days=120 - i * 30)))
    s.commit()

    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        r = TestClient(app).get("/api/subscriptions")
        assert r.status_code == 200
        body = r.json()
        assert body["adet"] == 1
        assert body["abonelikler"][0]["anahtar"] == "netflix"
        assert body["aylik_toplam"] == 59.99
    finally:
        app.dependency_overrides.clear()
        s.close()
