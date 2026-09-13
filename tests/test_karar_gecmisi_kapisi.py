"""
UX-027 / BUG #471 KAPISI — KARARA BAĞLANMIŞ AKSİYONLAR GÖRÜNÜR.

Ölçülen (13 Eyl 2026): canlıda 22 red + 10 onay + 1 başarısız vardı, hiçbiri arayüzde
görünmüyordu (Coach `handleActionResolved` listeden düşürüyor). `GET /api/actions/gecmis`:
pending OLMAYANLAR, en son karar en üstte, red gerekçesi `error_message`; limit sınırlı;
başka kullanıcının kaydı görünmez.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import ActionStatus, PendingAction, User


def _pa(db, uid, status, dk, reason=None, ozet="x"):
    db.add(PendingAction(user_id=uid, action_type="add_transaction", payload="{}", summary=ozet, status=status,
                         error_message=reason, resolved_at=(datetime(2026, 9, 13, 10, 0) + timedelta(minutes=dk)) if status != ActionStatus.pending else None))


def test_gecmis_yalniz_kararlanmis_sirali_gerekceli_ve_kapsamli(db_session, test_user):
    _pa(db_session, test_user.id, ActionStatus.rejected, 1, reason="yanlış hesap", ozet="red-1")
    _pa(db_session, test_user.id, ActionStatus.executed, 5, ozet="onay-2")
    _pa(db_session, test_user.id, ActionStatus.pending, 0, ozet="bekleyen")
    _pa(db_session, test_user.id, ActionStatus.failed, 3, reason="limit", ozet="hata-3")
    diger = User(name="d"); db_session.add(diger); db_session.commit()
    _pa(db_session, diger.id, ActionStatus.rejected, 9, ozet="baskasi")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        r = TestClient(app).get("/api/actions/gecmis?limit=2")
        r2 = TestClient(app).get("/api/actions/gecmis")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert [k["summary"] for k in r.json()] == ["onay-2", "hata-3"]          # en son karar önce, limit 2
    hepsi = r2.json()
    assert [k["summary"] for k in hepsi] == ["onay-2", "hata-3", "red-1"]     # bekleyen ve başkası yok
    assert hepsi[2]["status"] == "rejected" and hepsi[2]["error_message"] == "yanlış hesap"
