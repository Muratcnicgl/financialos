"""
BE-035 / BUG #443 KAPISI — RED KARARI DA İZ BIRAKIR (ONAYLA SİMETRİK).

Ölçülen (13 Eyl 2026): `approve` `ActionHistory` yazıyor (uygulanan değişiklik, önce/sonra),
`reject` yalnız `pending_actions.status/resolved_at/error_message` güncelliyordu; kim/ne zaman/
neden reddetti sorusu için ayrı bir defter yoktu. `action_history`'ye red yazmak yanlış olurdu
(o defter uygulanan aksiyonlarındır); doğru yer `audit_log`: `pending_actions` denetlenen
tablolara eklendi — durum geçişi ve red gerekçesi, onay tarafıyla aynı izle.

Kilitlenen: red → audit_log(entity=pending_actions, update) satırı; before `pending`, after
`rejected` + gerekçe; onay tarafındaki geçiş de aynı izi bırakır; `action_history` redde
yazılmaz (defter anlamı korunur).
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.denetim as denetim
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import ActionHistory, ActionStatus, AuditLog, Base, PendingAction, User


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)(); ses.add(User(id=1, name="u")); ses.commit()
    yield ses; ses.close()


def _bekleyen(ses):
    p = PendingAction(user_id=1, action_type="add_transaction", payload='{"amount": 1}', summary="x",
                      status=ActionStatus.pending)
    ses.add(p); ses.commit(); return p


def test_pending_actions_denetlenir_ve_gerekceli():
    assert "pending_actions" in denetim.denetlenen_tablolar()
    assert "red" in denetim.EK_DENETLENEN["pending_actions"]


def test_red_uc_uzerinden_iz_birakir_history_yazmaz(s):
    p = _bekleyen(s)
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        r = TestClient(app).post(f"/api/actions/{p.id}/reject", json={"reason": "yanlış hesap"})
        assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.clear()
    iz = s.query(AuditLog).filter_by(entity="pending_actions", entity_id=p.id, action="update").one()
    once, sonra = json.loads(iz.before_json), json.loads(iz.after_json)
    assert once["status"] == "pending" and sonra["status"] == "rejected"
    assert sonra["error_message"] == "yanlış hesap"
    assert iz.user_id == 1
    assert s.query(ActionHistory).count() == 0, "red uygulanan aksiyon defterine girmez"


def test_onay_gecisi_de_ayni_izi_birakir(s):
    p = _bekleyen(s)
    p.status = ActionStatus.approved; s.commit()
    iz = s.query(AuditLog).filter_by(entity="pending_actions", entity_id=p.id, action="update").one()
    assert json.loads(iz.after_json)["status"] == "approved"
