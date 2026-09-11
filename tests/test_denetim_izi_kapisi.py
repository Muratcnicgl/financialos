"""
OBS-020 / SEC-024 / BUG #408 KAPISI — FİNANSAL KAYDIN GÜNCELLEME/SİLME İZİ VAR.

Ölçülen (12 Eyl 2026): `ActionHistory` yalnız koç aksiyonlarını tutuyordu; panelden yapılan
DELETE/PUT (hesap silme, bakiye düzeltme, borç kapama) hiçbir yerde kalmıyordu. Backlog
"router DELETE audit yok" diye 60+ gündür taşıyordu.

Kilitlenen: kanca ORM flush'ta (hangi yoldan gelirse gelsin); denetlenen tablolar
KAYNAKTAN türetilir (user_id + Numeric), muaflar gerekçeli; delete tüm satırı, update
yalnız değişen alanları (eski/yeni) taşır; ekleme denetlenmez; korelasyon kimliği taşınır;
KVKK silmesi izi de götürür (user_id); saklama 365 gün.
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
from app.models import Account, AccountType, AuditLog, Base, PersonalDebt, User


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)()
    ses.add(User(id=1, name="u")); ses.commit()
    yield ses
    ses.close()


def test_denetlenen_tablolar_kaynaktan_turetilir_muaflar_gerekceli():
    t = denetim.denetlenen_tablolar()
    assert {"accounts", "transactions", "personal_debts", "goals", "recurring_incomes",
            "recurring_expenses", "envelopes", "wishlist_items"} <= t
    assert not (t & set(denetim.MUAF))
    assert "audit_log" not in t, "iz kendini denetlemez"
    assert "master_checkpoints" in t, "BUG #414: para kuralları denetlenir (DATA-034)"
    for ad, neden in denetim.EK_DENETLENEN.items():
        assert ad in Base.metadata.tables and len(neden) > 20
    for ad, neden in denetim.MUAF.items():
        assert ad in Base.metadata.tables and len(neden) > 20, f"ölü ya da gerekçesiz muafiyet: {ad}"


def test_silme_tum_satiri_yazar_ekleme_yazmaz(s):
    acc = Account(user_id=1, name="Kumbara", account_type=AccountType.cash, balance=1234.5)
    s.add(acc); s.commit()
    assert s.query(AuditLog).count() == 0, "ekleme denetlenmez"
    s.delete(acc); s.commit()
    iz = s.query(AuditLog).one()
    assert (iz.entity, iz.action, iz.entity_id, iz.user_id) == ("accounts", "delete", acc.id, 1)
    once = json.loads(iz.before_json)
    assert once["name"] == "Kumbara" and once["balance"].startswith("1234.5")


def test_guncelleme_yalniz_degisen_alanlari_yazar(s):
    d = PersonalDebt(user_id=1, counterparty="Ahmet", direction="receivable", amount=100)
    s.add(d); s.commit()
    d.amount = 250; d.is_paid = True
    s.commit()
    iz = s.query(AuditLog).filter_by(action="update").one()
    once, sonra = json.loads(iz.before_json), json.loads(iz.after_json)
    assert set(once) == {"amount", "is_paid"} and set(sonra) == {"amount", "is_paid"}
    assert once["is_paid"] is False and sonra["is_paid"] is True
    assert once["amount"].startswith("100") and sonra["amount"].startswith("250")
    d.counterparty = "Ahmet"   # değişmeyen atama → iz yok
    s.commit()
    assert s.query(AuditLog).filter_by(action="update").count() == 1


def test_router_uzerinden_silme_de_yakalanir(s):
    acc = Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=10)
    s.add(acc); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        r = TestClient(app).delete(f"/api/accounts/{acc.id}")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code in (200, 204), r.text
    iz = s.query(AuditLog).filter_by(entity="accounts", action="delete").one()
    assert iz.istek_id and len(iz.istek_id) >= 8, "korelasyon kimliği taşınmalı (BUG #280)"


def test_kvkk_silmesi_izi_de_goturur():
    """`audit_log` user_id taşır → kvkk erasure 'user_id taşıyan her tablo' kuralıyla siler."""
    t = Base.metadata.tables["audit_log"]
    assert "user_id" in t.c and not t.c.user_id.nullable


def test_muafiyet_kurali_isliyor(s):
    from app.models import NetWorthSnapshot
    from datetime import date
    snap = NetWorthSnapshot(user_id=1, snapshot_date=date(2026, 9, 1), net_worth_seen=1, net_worth_full=1, cash=1,
                            card_debt=0, loan_debt=0, investment_value=0)
    s.add(snap); s.commit(); snap.cash = 2; s.commit(); s.delete(snap); s.commit()
    assert s.query(AuditLog).count() == 0


def test_aktorsuz_kayit_flushu_dusurmez(s):
    """Goal.user_id nullable (DATA-009): aktörsüz satırda iz yazılmaz ama işlem de düşmez."""
    from app.models import Goal
    g = Goal(user_id=None, title="x", goal_type="savings", target_amount=100)
    s.add(g); s.commit(); g.target_amount = 200; s.commit(); s.delete(g); s.commit()
    assert s.query(AuditLog).count() == 0


def test_para_kurali_degisikligi_iz_birakir(s):
    """DATA-034: MasterCheckpoint'in gevşetilmesi/silinmesi bakiye kadar izlenir (BUG #414)."""
    from app.models import CheckpointType, MasterCheckpoint
    mc = MasterCheckpoint(user_id=1, title="Kira", description="kira parasına dokunma",
                          checkpoint_type=list(CheckpointType)[0], rule_type="min_cash_floor",
                          rule_params='{"amount": 5000}')
    s.add(mc); s.commit()
    mc.rule_params = '{"amount": 100}'; mc.is_active = False; s.commit()
    iz = s.query(AuditLog).filter_by(entity="master_checkpoints", action="update").one()
    assert set(json.loads(iz.before_json)) == {"rule_params", "is_active"}
    s.delete(mc); s.commit()
    assert s.query(AuditLog).filter_by(entity="master_checkpoints", action="delete").count() == 1
