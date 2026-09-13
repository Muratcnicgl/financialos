"""
DVIZ-007 / BUG #460 KAPISI — FON FİYAT GEÇMİŞİ UCU.

Ölçülen (13 Eyl 2026): `price_history` gece işiyle günlük fiyat biriktiriyordu (canlıda TP2
2 gün) ama hiçbir uç okumuyordu. Kilitlenen: günde TEK fiyat, kaynak önceliği manual > tefas
> yfinance; pencere dışı satır yok; `cost_per_lot` referansı; yetki HESAP SAHİPLİĞİ ile —
başka kullanıcının hesabı 404, fon kodu olmayan hesap 404.
"""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Account, AccountType, PriceHistory, PriceSource, User

BUGUN = date(2026, 9, 13)


def _kur(db, uid):
    acc = Account(user_id=uid, name="Fon", account_type=AccountType.investment, balance=0,
                  fund_code="TP2", lot_count=10, cost_per_lot=4.5)
    db.add(acc); db.commit()
    db.add_all([
        PriceHistory(fund_code="TP2", price_date=date(2026, 9, 10), source=PriceSource.TEFAS, close_price=5.0),
        PriceHistory(fund_code="TP2", price_date=date(2026, 9, 11), source=PriceSource.TEFAS, close_price=5.1),
        PriceHistory(fund_code="TP2", price_date=date(2026, 9, 11), source=PriceSource.MANUAL, close_price=5.3),   # aynı gün: manual kazanır
        PriceHistory(fund_code="TP2", price_date=date(2026, 9, 12), source=PriceSource.YFINANCE, close_price=5.2),
        PriceHistory(fund_code="TP2", price_date=date(2025, 1, 1), source=PriceSource.TEFAS, close_price=1.0),      # pencere dışı
    ])
    db.commit()
    return acc


def _istemci(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_gunde_tek_fiyat_oncelik_ve_pencere(db_session, test_user, monkeypatch):
    import app.routers.reports as rp
    monkeypatch.setattr(rp, "user_today", lambda u: BUGUN)
    acc = _kur(db_session, test_user.id)
    try:
        r = _istemci(db_session, test_user).get(f"/api/reports/fund-history?account_id={acc.id}&days=30")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["fund_code"] == "TP2" and g["cost_per_lot"] == 4.5
    assert [(i["date"], i["price"], i["source"]) for i in g["items"]] == [
        ("2026-09-10", 5.0, "tefas"), ("2026-09-11", 5.3, "manual"), ("2026-09-12", 5.2, "yfinance")]


def test_yetki_hesap_sahipligi_ve_fon_kodu(db_session, test_user):
    acc = _kur(db_session, test_user.id)
    diger = User(name="d"); db_session.add(diger); db_session.commit()
    nakit = Account(user_id=test_user.id, name="N", account_type=AccountType.cash, balance=0); db_session.add(nakit); db_session.commit()
    try:
        assert _istemci(db_session, diger).get(f"/api/reports/fund-history?account_id={acc.id}").status_code == 404
        assert _istemci(db_session, test_user).get(f"/api/reports/fund-history?account_id={nakit.id}").status_code == 404
    finally:
        app.dependency_overrides.clear()
