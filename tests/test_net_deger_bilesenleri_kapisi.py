"""
DVIZ-012 / BUG #458 KAPISI — NET DEĞER TRENDİ BİLEŞENLERİNİ TAŞIR.

Ölçülen (13 Eyl 2026): `NetWorthSnapshot` nakit/kart/kredi/yatırım/alacağı günlerdir ayrı
saklıyordu, `net-worth-trend` yalnız üç toplamı döndürüyordu. Kilitlenen: her kalem
`cash/card_debt/loan_debt/investment_value/receivables` taşır; sağlama
`net_worth_full − net_worth_seen == receivables` ve `net_worth_seen == cash + investment − card − loan`
(snapshot'ın kendi tanımı) — uç kopyalarken bir alanı karıştırırsa burada kırılır.
"""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import NetWorthSnapshot


def test_trend_bilesenleri_ve_saglama(db_session, test_user, monkeypatch):
    import app.routers.reports as rp
    monkeypatch.setattr(rp, "user_today", lambda u: date(2026, 9, 13))
    db_session.add(NetWorthSnapshot(user_id=test_user.id, snapshot_date=date(2026, 9, 12),
                                    cash=1000, investment_value=500, card_debt=300, loan_debt=200,
                                    receivables=150, net_worth_seen=1000, net_worth_full=1150))
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        r = TestClient(app).get("/api/reports/net-worth-trend?days=7")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    k = r.json()["items"][-1]
    assert (k["cash"], k["card_debt"], k["loan_debt"], k["investment_value"], k["receivables"]) == (1000, 300, 200, 500, 150)
    assert k["net_worth_full"] - k["net_worth_seen"] == k["receivables"]
    assert k["net_worth_seen"] == k["cash"] + k["investment_value"] - k["card_debt"] - k["loan_debt"]
