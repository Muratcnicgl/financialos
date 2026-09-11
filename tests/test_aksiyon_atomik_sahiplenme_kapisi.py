"""
SEC-023 / RESIL-003 / BUG #413 KAPISI — ONAY GEÇİŞİ ATOMİK TEK YÖN.

Ölçülen (12 Eyl 2026): `execute_pending_action` durumu OKUYUP karar veriyor, işleyiciyi
koşturup SONRA `executed` yazıyordu. İki eşzamanlı onay ikisi de "pending" görür, ikisi
de işler — çift işlem (aynı harcama iki kez, bakiye iki kez düşer). "status!=pending replay
bloklu" savunması yalnız ARDIŞIK tekrarı bloklar, eşzamanlıyı değil.

Kilitlenen: tek koşullu UPDATE (`WHERE status='pending'`) satırı sahiplenir; sahiplenme
işleyiciden ÖNCE gerçekleşir (işleyici çalışırken ikinci onay 409); kaybeden hiçbir şey
işlemez; kazanan `executed`, düşen `failed`.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import action_executor as ae
from app.models import Account, AccountType, ActionStatus, Base, PendingAction, User


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)(); ses.add(User(id=1, name="u")); ses.commit()
    yield ses; ses.close()


def _pending(s, acc_id):
    p = PendingAction(user_id=1, action_type="add_transaction", summary="t", status=ActionStatus.pending,
                      payload=json.dumps({"transaction_type": "expense", "amount": 100, "account_id": acc_id,
                                          "auto_update_balance": True}))
    s.add(p); s.commit(); s.refresh(p)
    return p


def test_isleyici_calisirken_ikinci_onay_409_ve_tek_islem(s, monkeypatch):
    acc = Account(user_id=1, name="Kumbara", account_type=AccountType.cash, balance=1000)
    s.add(acc); s.commit()
    p = _pending(s, acc.id)
    gercek = ae.ACTION_HANDLERS["add_transaction"]
    ic_sonuc = {}

    def yaris_handler(db, user_id, payload):
        # işleyici koşarken "ikinci istek" gelir: sahiplenme daha önce yapıldıysa 'zaten' döner
        ic_sonuc["ikinci"] = ae.execute_pending_action(db=db, action_id=p.id, user_id=1)
        return gercek(db, user_id, payload)

    monkeypatch.setitem(ae.ACTION_HANDLERS, "add_transaction", yaris_handler)
    birinci = ae.execute_pending_action(db=s, action_id=p.id, user_id=1)
    assert birinci["success"] is True, birinci
    assert ic_sonuc["ikinci"]["success"] is False and ic_sonuc["ikinci"]["kod"] == "zaten"
    s.refresh(acc); s.refresh(p)
    assert float(acc.balance) == 900.0, "işlem iki kez uygulandı"
    assert p.status == ActionStatus.executed


def test_sahiplenme_kaybedeni_hicbir_sey_islemez(s):
    acc = Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=500)
    s.add(acc); s.commit()
    p = _pending(s, acc.id)
    # Başka bir istek satırı çoktan sahiplenmiş olsun (approved)
    p.status = ActionStatus.approved; s.commit()
    r = ae.execute_pending_action(db=s, action_id=p.id, user_id=1)
    assert r["success"] is False and r["kod"] == "zaten"
    s.refresh(acc); assert float(acc.balance) == 500.0


def test_dusen_isleyici_failed_birakir_pending_degil(s, monkeypatch):
    acc = Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=500)
    s.add(acc); s.commit()
    p = _pending(s, acc.id)
    monkeypatch.setitem(ae.ACTION_HANDLERS, "add_transaction", lambda db, u, pl: (_ for _ in ()).throw(RuntimeError("boom")))
    r = ae.execute_pending_action(db=s, action_id=p.id, user_id=1)
    assert r["success"] is False
    s.refresh(p); assert p.status == ActionStatus.failed
