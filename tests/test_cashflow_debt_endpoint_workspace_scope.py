"""
D03 (BUG #223) — `/api/cashflow/forecast` ve `/api/debt-strategy/*` UÇLARI workspace
bağlamını hiç kurmuyordu.

BUG #165 motor katmanını (`app/cashflow.py`, `app/debt_strategy.py` → `_scope`) düzeltti,
ama HTTP uçları `workspace_scope(ws_id)` bloğuna hiç girmiyordu. contextvar boş kaldığı
için `_scope` her zaman legacy `user_id` dalına düşüyordu. Sonuç (aile workspace'i seçiliyken):

- cockpit "0 TL borç / 50.000 nakit" derken debt-strategy KİŞİSEL iki borcu listeliyor,
  cashflow açılışı 60.000 (kişisel + aile toplanmış) diyordu → aynı ekranda çelişen rakamlar
  ve YANLIŞ borç kümesi üzerinde koşan snowball/avalanche + konsolidasyon tavsiyeleri.
- Bu uçlar üyelik doğrulaması da yapmıyordu: üye OLUNMAYAN bir workspace id'si ile 200
  dönüyorlardı (cockpit doğru şekilde 403 veriyor).

L11 dersi: motor katmanında kanıtlanmış kapsam, uç katmanında bağlanmamışsa YOKTUR —
mevcut test (`tests/test_cashflow_workspace_scope.py`) `generate_forecast`'i doğrudan
`with workspace_scope(...)` içinde çağırdığı için ucun kör olduğunu göremiyordu. Bu dosya
kapıyı HTTP seviyesinde kurar.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Workspace, WorkspaceMembership, WorkspaceRole,
    Account, AccountType, RecurringIncome,
)


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
    """u1: kişisel ws (10.000 nakit + 2 kişisel borç) + aile ws (50.000 nakit + 2 aile borcu).

    u2 (eş): aile ws'de editor, kendi kişisel workspace'i YOK (üyelik dışı erişim testi için).
    """
    u1 = User(name="murat", email="m@x.com")
    u2 = User(name="es", email="es@x.com")
    db.add_all([u1, u2])
    db.commit()

    kisisel = Workspace(owner_user_id=u1.id, name="Kişisel", is_personal=True)
    aile = Workspace(owner_user_id=u1.id, name="Aile", is_personal=False)
    db.add_all([kisisel, aile])
    db.commit()
    db.add_all([
        WorkspaceMembership(workspace_id=kisisel.id, user_id=u1.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=aile.id, user_id=u1.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=aile.id, user_id=u2.id, role=WorkspaceRole.editor),
    ])
    db.add_all([
        Account(user_id=u1.id, workspace_id=kisisel.id, name="Kişisel kasa",
                account_type=AccountType.cash, balance=10000.0),
        Account(user_id=u1.id, workspace_id=kisisel.id, name="KISISEL-KART",
                account_type=AccountType.credit_card, balance=20000.0, interest_rate=4.0),
        Account(user_id=u1.id, workspace_id=kisisel.id, name="KISISEL-KREDI",
                account_type=AccountType.loan, balance=40000.0,
                interest_rate=2.5, monthly_payment=3000.0),
        Account(user_id=u1.id, workspace_id=aile.id, name="Aile kasası",
                account_type=AccountType.cash, balance=50000.0),
        Account(user_id=u1.id, workspace_id=aile.id, name="AILE-KART",
                account_type=AccountType.credit_card, balance=15000.0, interest_rate=4.0),
        Account(user_id=u1.id, workspace_id=aile.id, name="AILE-KREDI",
                account_type=AccountType.loan, balance=30000.0,
                interest_rate=2.0, monthly_payment=2500.0),
        RecurringIncome(user_id=u1.id, workspace_id=aile.id, name="Aile kirası",
                        amount=7000.0, day_of_month=5, is_active=True),
    ])
    db.commit()
    return {"u1": u1, "u2": u2, "kisisel": kisisel, "aile": aile}


@pytest.fixture
def client(db, env):
    app.dependency_overrides[get_db] = lambda: db
    state = {"user": env["u1"]}
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    c = TestClient(app)
    c._who = state
    yield c
    app.dependency_overrides.clear()


def _as(client, user):
    client._who["user"] = user


def _ws(env, key):
    return {"X-Workspace-Id": str(env[key].id)}


# ============================================================
# CASHFLOW FORECAST
# ============================================================

def test_forecast_aile_baglaminda_yalniz_aile_kasasi(client, env):
    """Aile başlığıyla açılış bakiyesi 50.000 olmalı — 60.000 ise kişisel kasa sızmıştır."""
    r = client.get("/api/cashflow/forecast?days=30", headers=_ws(env, "aile"))
    assert r.status_code == 200, r.text
    acilis = r.json()["summary"]["opening_balance"]
    assert acilis == pytest.approx(50000.0), (
        f"Aile bağlamında açılış {acilis} — uç workspace kapsamını kurmuyor "
        "(kişisel 10.000 + aile 50.000 toplanmış olabilir)"
    )


def test_forecast_baslik_yoksa_kisisel_workspace(client, env):
    """Başlık yoksa personal workspace'e düşülür → yalnız kişisel kasa."""
    r = client.get("/api/cashflow/forecast?days=30")
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["opening_balance"] == pytest.approx(10000.0)


def test_forecast_aile_gelirini_kisisel_baglamda_saymaz(client, env):
    """Aile düzenli geliri yalnız aile bağlamında projeksiyona girer."""
    aile = client.get("/api/cashflow/forecast?days=60", headers=_ws(env, "aile")).json()
    kisisel = client.get("/api/cashflow/forecast?days=60").json()
    assert aile["summary"]["total_receivable"] > 0
    assert kisisel["summary"]["total_receivable"] == pytest.approx(0.0), \
        "Aile geliri kişisel projeksiyona sızdı"


def test_forecast_uye_olunmayan_workspace_403(client, env):
    """Var olmayan/üye olunmayan workspace id'si 403 vermeli (cockpit ile aynı davranış)."""
    r = client.get("/api/cashflow/forecast?days=30", headers={"X-Workspace-Id": "9999"})
    assert r.status_code == 403, f"Beklenen 403, gelen {r.status_code}"


# ============================================================
# DEBT STRATEGY
# ============================================================

def test_compare_aile_baglaminda_yalniz_aile_borclari(client, env):
    """Aile başlığıyla snowball/avalanche YALNIZ aile borçları üzerinde koşmalı."""
    r = client.get("/api/debt-strategy/compare", headers=_ws(env, "aile"))
    assert r.status_code == 200, r.text
    isimler = sorted(d["name"] for d in r.json()["debts"])
    assert isimler == ["AILE-KART", "AILE-KREDI"], (
        f"Aile bağlamında listelenen borçlar {isimler} — kişisel borçlar sızmış olabilir"
    )


def test_compare_baslik_yoksa_kisisel_borclar(client, env):
    """Başlık yoksa personal workspace → yalnız kişisel borçlar."""
    r = client.get("/api/debt-strategy/compare")
    assert r.status_code == 200, r.text
    isimler = sorted(d["name"] for d in r.json()["debts"])
    assert isimler == ["KISISEL-KART", "KISISEL-KREDI"]


def test_consolidation_aile_baglaminda_aile_borclarini_toplar(client, env):
    """Konsolidasyon toplamı aile borçlarının toplamı (45.000) olmalı, kişiselinki değil."""
    r = client.get("/api/debt-strategy/consolidation?rate=2.0&term=24",
                   headers=_ws(env, "aile"))
    assert r.status_code == 200, r.text
    toplam = r.json()["toplam_bakiye"]
    assert toplam == pytest.approx(45000.0), (
        f"Aile bağlamında konsolide edilen borç {toplam} — beklenen 45.000 "
        "(kişisel 60.000 sızmış olabilir)"
    )


def test_opportunity_cost_aile_baglaminda_aile_borcunu_hedefler(client, env):
    """Fırsat maliyeti en yüksek faizli AİLE borcunu hedeflemeli (AILE-KART)."""
    r = client.get("/api/debt-strategy/opportunity-cost?amount=5000",
                   headers=_ws(env, "aile"))
    assert r.status_code == 200, r.text
    hedef = r.json()["hedef_borc"]
    assert hedef == "AILE-KART", (
        f"Aile bağlamında hedeflenen borç {hedef!r} — kişisel borç kümesi sızmış olabilir"
    )


@pytest.mark.parametrize("yol", [
    "/api/debt-strategy/compare",
    "/api/debt-strategy/consolidation?rate=2.0&term=24",
    "/api/debt-strategy/opportunity-cost?amount=5000",
])
def test_debt_strategy_uye_olunmayan_workspace_403(client, env, yol):
    """Üyelik doğrulaması: üye olunmayan workspace id'si 403."""
    r = client.get(yol, headers={"X-Workspace-Id": "9999"})
    assert r.status_code == 403, f"{yol} → beklenen 403, gelen {r.status_code}"


def test_ikinci_kullanici_aile_baglaminda_aile_borclarini_gorur(client, env):
    """Eş (aile ws editor) aile bağlamında ORTAK borçları görmeli — kendi kişisel kümesini değil.

    Denetim kanıtı: eski davranışta eş yalnız kendi kişisel kartını görüyordu, gerçek ortak
    borç (AILE-KREDI) hiç listelenmiyordu.
    """
    _as(client, env["u2"])
    r = client.get("/api/debt-strategy/compare", headers=_ws(env, "aile"))
    assert r.status_code == 200, r.text
    isimler = sorted(d["name"] for d in r.json()["debts"])
    assert isimler == ["AILE-KART", "AILE-KREDI"]
