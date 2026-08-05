"""
D03b (BUG #224) — premortem ve simülasyon uçları workspace bağlamı kurmuyordu.

D03 (BUG #223) kapatılırken yapılan SINIF taraması (L11: "bir örnek bulunduysa sınıf
taranmadan kapatılmaz") `app/routers/*.py` içinde kapsam-duyarlı motor çağıran ama
workspace bağlamı kurmayan iki uç daha ölçtü:

- `POST /api/premortem/{id}` → `build_cockpit_snapshot` → `generate_cockpit` (kapsam-duyarlı,
  ama contextvar boş → legacy `user_id` dalı).
- `POST /api/simulate/{id}` → `simulate_action` → `_load_world` (motorun KENDİSİ hiç
  workspace-farkında değildi: 3 sorgu da ham `Model.user_id == user_id`).

Etki: aile (paylaşımlı) workspace'i seçiliyken bir aksiyonun ön-ölüm analizi ve 3-ufuklu
simülasyonu KİŞİSEL manzara üzerinde koşuyordu → kullanıcı ekrandaki aile rakamlarıyla
çelişen bir risk/etki analizi okuyup ona göre karar veriyordu.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Workspace, WorkspaceMembership, WorkspaceRole,
    Account, AccountType, ActionStatus, PendingAction,
)
from app.premortem import PremortemResult, PremortemScenario


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def env(db):
    """u1: kişisel ws (10.000 nakit) + aile ws (50.000 nakit). Aile ws'de bekleyen aksiyon."""
    u1 = User(name="murat", email="m@x.com")
    db.add(u1)
    db.commit()

    kisisel = Workspace(owner_user_id=u1.id, name="Kişisel", is_personal=True)
    aile = Workspace(owner_user_id=u1.id, name="Aile", is_personal=False)
    db.add_all([kisisel, aile])
    db.commit()
    db.add_all([
        WorkspaceMembership(workspace_id=kisisel.id, user_id=u1.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=aile.id, user_id=u1.id, role=WorkspaceRole.owner),
    ])
    kisisel_kasa = Account(user_id=u1.id, workspace_id=kisisel.id, name="Kişisel kasa",
                           account_type=AccountType.cash, balance=10000.0)
    aile_kasa = Account(user_id=u1.id, workspace_id=aile.id, name="Aile kasası",
                        account_type=AccountType.cash, balance=50000.0)
    db.add_all([kisisel_kasa, aile_kasa])
    db.commit()

    action = PendingAction(
        user_id=u1.id,
        workspace_id=aile.id,
        action_type="add_transaction",
        payload=json.dumps({
            "amount": 1500.0,
            "account_id": aile_kasa.id,
            "transaction_type": "expense",
            "auto_update_balance": True,
            "category": "market",
        }),
        summary="Market harcaması",
        status=ActionStatus.pending,
    )
    db.add(action)
    db.commit()
    return {"u1": u1, "kisisel": kisisel, "aile": aile, "action": action,
            "kisisel_kasa": kisisel_kasa, "aile_kasa": aile_kasa}


@pytest.fixture
def client(db, env):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: env["u1"]
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _ws(env, key):
    return {"X-Workspace-Id": str(env[key].id)}


# ============================================================
# SİMÜLASYON
# ============================================================

def test_simulasyon_aile_baglaminda_aile_kasasini_kullanir(client, env):
    """Aile bağlamı: baseline 50.000, harcama uygulanınca T+0 = 48.500."""
    r = client.post(f"/api/simulate/{env['action'].id}", headers=_ws(env, "aile"))
    assert r.status_code == 200, r.text
    govde = r.json()
    assert govde["ok"] is True, govde["message"]
    assert govde["baseline"]["nakit_kasa"] == pytest.approx(50000.0), (
        f"Aile bağlamında baseline nakit {govde['baseline']['nakit_kasa']} — "
        "kişisel kasa (10.000) toplanmış olabilir"
    )
    t0 = govde["horizons"][0]
    assert t0["nakit_kasa"] == pytest.approx(48500.0)


def test_simulasyon_baslik_yoksa_kisisel_workspace(client, env):
    """Başlık yoksa personal workspace: yalnız kişisel kasa görülür.

    Aksiyonun hedefi AİLE hesabı olduğu için kişisel bağlamda bulunamaz (ok=False) —
    bu, dünyanın gerçekten kapsandığının doğrudan kanıtı.
    """
    r = client.post(f"/api/simulate/{env['action'].id}")
    assert r.status_code == 200, r.text
    govde = r.json()
    assert govde["baseline"]["nakit_kasa"] == pytest.approx(10000.0), (
        f"Kişisel bağlamda baseline nakit {govde['baseline']['nakit_kasa']} — "
        "aile kasası (50.000) sızmış olabilir"
    )
    assert govde["ok"] is False and "bulunamadi" in govde["message"].lower(), (
        f"Aile hesabı kişisel bağlamda görülebiliyor: {govde['message']!r}"
    )


def test_simulasyon_uye_olunmayan_workspace_403(client, env):
    r = client.post(f"/api/simulate/{env['action'].id}", headers={"X-Workspace-Id": "9999"})
    assert r.status_code == 403, f"Beklenen 403, gelen {r.status_code}"


# ============================================================
# PREMORTEM
# ============================================================

def _mock_result(action_id: int) -> PremortemResult:
    return PremortemResult(
        action_id=action_id,
        scenarios=[
            PremortemScenario(
                id=f"S{i}",
                title=f"Senaryo {i}",
                probability_label="orta",
                impact_tl=-500.0,
                narrative="Bu aksiyon basarisiz oldu cunku test sebebi yeterli uzunlukta yazildi.",
                mitigation="Test mitigation aksiyonu yazildi.",
            )
            for i in range(1, 4)
        ],
        provider_used="fake",
        model_name="fake-model",
    )


def test_premortem_aile_baglaminda_aile_manzarasini_gonderir(client, env):
    """LLM'e giden cockpit snapshot'ı aile nakdini (50.000) taşımalı, 60.000'i değil."""
    yakalanan = {}

    def _fake(action_id, action_context, cockpit_snapshot):
        yakalanan["snapshot"] = cockpit_snapshot
        return _mock_result(action_id)

    with patch("app.routers.premortem.generate_premortem", side_effect=_fake):
        r = client.post(f"/api/premortem/{env['action'].id}", headers=_ws(env, "aile"))

    assert r.status_code == 200, r.text
    nakit = yakalanan["snapshot"]["cash_tl"]
    assert nakit == pytest.approx(50000.0), (
        f"Aile bağlamında premortem'e giden nakit {nakit} — kişisel kasa sızmış olabilir"
    )


def test_premortem_baslik_yoksa_kisisel_manzara(client, env):
    """Başlık yoksa personal workspace snapshot'ı gider."""
    yakalanan = {}

    def _fake(action_id, action_context, cockpit_snapshot):
        yakalanan["snapshot"] = cockpit_snapshot
        return _mock_result(action_id)

    with patch("app.routers.premortem.generate_premortem", side_effect=_fake):
        r = client.post(f"/api/premortem/{env['action'].id}")

    assert r.status_code == 200, r.text
    assert yakalanan["snapshot"]["cash_tl"] == pytest.approx(10000.0)


def test_premortem_uye_olunmayan_workspace_403(client, env):
    with patch("app.routers.premortem.generate_premortem", side_effect=AssertionError("LLM çağrılmamalı")):
        r = client.post(f"/api/premortem/{env['action'].id}", headers={"X-Workspace-Id": "9999"})
    assert r.status_code == 403, f"Beklenen 403, gelen {r.status_code}"


# ============================================================
# MOTOR KATMANI (simulation_engine köprüsü)
# ============================================================

def test_simulation_engine_kapsam_koprusunu_kullanir(db, env):
    """`_load_world` workspace kapsamına saygı duymalı; kapsam yoksa legacy user_id (köprü)."""
    from datetime import date
    from app.simulation_engine import _load_world
    from app.scope import workspace_scope

    with workspace_scope(env["aile"].id):
        world = _load_world(db, env["u1"].id, date(2026, 8, 5))
    assert [a.name for a in world.accounts] == ["Aile kasası"]

    with workspace_scope(env["kisisel"].id):
        world = _load_world(db, env["u1"].id, date(2026, 8, 5))
    assert [a.name for a in world.accounts] == ["Kişisel kasa"]

    # Köprü regresyonu: kapsam yokken kullanıcının TÜM hesapları (eski davranış)
    world = _load_world(db, env["u1"].id, date(2026, 8, 5))
    assert sorted(a.name for a in world.accounts) == ["Aile kasası", "Kişisel kasa"]
