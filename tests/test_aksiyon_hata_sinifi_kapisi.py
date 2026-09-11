"""
BE-011 / BUG #402 KAPISI — YÜRÜTÜCÜ HATA SINIFI HTTP STATÜSÜNE TAŞINIR.

Ölçülen (11 Eyl 2026): approve her başarısızlığı 422'ye, reject her başarısızlığı 404'e
çeviriyordu. "Kuralın engelledi" (politika), "zaten uygulandı" (durum çatışması) ve
"hesap yok" (girdi) istemciye aynı koddan geliyordu; "zaten reddedildi" 404 geliyordu —
aksiyon vardı. Madde 60+ gündür "kısmen" (Aksiyon: istisna hiyerarşisi + merkezî handler).

Karar: yürütücünün dict sözleşmesi KORUNUR (ADR-001 enforcement kod seviyesinde; istisna
hiyerarşisi her handler'ı değiştirirdi); sınıf yürütücüde etiketlenir (`rule_blocked`,
`kod`), statü tek yerde (`_yurutucu_hatasi`) çevrilir:
  rule_blocked → 403 · kod="zaten" → 409 · kod="bulunamadi" → 404 · diğer → 422.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Account, AccountType, ActionStatus, Base, PendingAction, User
from app.routers import actions as actions_router
from app.user_rules import RuleViolation


@pytest.fixture
def ortam():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="u")); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        yield s, TestClient(app)
    finally:
        app.dependency_overrides.clear(); s.close()


def _pending(s, payload, status=ActionStatus.pending):
    p = PendingAction(user_id=1, action_type="add_transaction", payload=json.dumps(payload),
                      summary="t", status=status)
    s.add(p); s.commit(); s.refresh(p)
    return p


def test_cevirici_dort_sinif():
    h = actions_router._yurutucu_hatasi
    assert h({"success": False, "rule_blocked": True, "error": "x"}, "v").status_code == 403
    assert h({"success": False, "kod": "zaten", "error": "x"}, "v").status_code == 409
    assert h({"success": False, "kod": "bulunamadi", "error": "x"}, "v").status_code == 404
    assert h({"success": False, "message": "hesap yok"}, "v").status_code == 422
    assert h({"success": False}, "varsayilan").detail == "varsayilan"


def test_kural_engeli_403_gercek_yol(ortam, monkeypatch):
    """`enforce_user_rules` ihlal fırlatır → yürütücü rule_blocked → 403 (422 değil)."""
    s, c = ortam
    acc = Account(user_id=1, name="Kumbara", account_type=AccountType.cash, balance=100)
    s.add(acc); s.commit()
    p = _pending(s, {"transaction_type": "expense", "amount": 10, "account_id": acc.id})

    def ihlal(*a, **k):
        raise RuleViolation("Kira", "kira parasına dokunma")
    monkeypatch.setattr("app.user_rules.enforce_user_rules", ihlal)
    r = c.post(f"/api/actions/{p.id}/approve")
    assert r.status_code == 403, r.text
    assert "Kira" in r.json()["detail"]


def test_zaten_uygulanmis_409_ve_reddedilmis_409(ortam):
    s, c = ortam
    p = _pending(s, {"transaction_type": "expense", "amount": 10}, status=ActionStatus.executed)
    assert c.post(f"/api/actions/{p.id}/approve").status_code == 409
    q = _pending(s, {"transaction_type": "expense", "amount": 10}, status=ActionStatus.rejected)
    assert c.post(f"/api/actions/{q.id}/reject").status_code == 409


def test_girdi_hatasi_422_ve_yok_404(ortam):
    s, c = ortam
    p = _pending(s, {"transaction_type": "expense", "amount": 10, "account_id": 99999})
    assert c.post(f"/api/actions/{p.id}/approve").status_code == 422
    assert c.post("/api/actions/99999/approve").status_code == 404
    assert c.post("/api/actions/99999/reject").status_code == 404
