"""
UX-024 (BUG #479): borç planı hedefe bağlanır — "Bu planı benimse".

Ölçüm (14 Eyl 2026): Borç Stratejisi paneli iki planı karşılaştırıyor ama taahhüt üretmiyordu;
debt_freedom hedefinin tahmini bitişi ise HER ZAMAN Snowball + ekstra 0 ile hesaplanıyordu —
kullanıcı Avalanche + 1.500 TL planlasa bile hedef kartı başka bir tarih gösteriyordu.

Kilitlenen sözleşme:
  1. `plan` yalnız debt_freedom hedefine bağlanır (cash_target → 422),
  2. yaratımda ve PATCH'te kayıt sözlüğü saklanır ve GoalRead'de döner,
  3. projeksiyon benimsenen planı kullanır: ekstra ödeme bitiş tarihini ÖNE çeker,
  4. arayüz: iki kartta da "Bu planı benimse"; köprü tek kaynak `lib/borcPlani.js`;
     mevcut hedef varsa güncellenir, yoksa yaratılır.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.goal_engine import plan_secimi
from app.main import app
from app.models import Account, AccountType, Base, Goal, User

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=20000))
    s.add(Account(user_id=1, name="Kredi", account_type=AccountType.loan, balance=120000,
                  interest_rate=3.5, monthly_payment=6000, remaining_installments=24))
    s.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card, balance=30000,
                  credit_limit=40000, interest_rate=4.0))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _hedef(client, plan=None, tip="debt_freedom"):
    govde = {"goal_type": tip, "title": "Borçsuz ol", "target_amount": "150000"}
    if plan is not None:
        govde["plan"] = plan
    return client.post("/api/goals", json=govde)


def test_plan_yalniz_debt_freedom(client):
    r = _hedef(client, {"strateji": "avalanche", "aylik_ekstra": 1500}, tip="cash_target")
    assert r.status_code == 422, r.text


def test_plan_yaratimda_saklanir_ve_doner(client):
    r = _hedef(client, {"strateji": "avalanche", "aylik_ekstra": "1500"})
    assert r.status_code == 201, r.text
    assert r.json()["plan"] == {"strateji": "avalanche", "aylik_ekstra": 1500.0}
    # plansız hedef: alan null
    assert _hedef(client).json()["plan"] is None


def test_plan_patch_ile_guncellenir_ve_sinirlari_var(client):
    gid = _hedef(client).json()["id"]
    r = client.patch(f"/api/goals/{gid}", json={"plan": {"strateji": "snowball", "aylik_ekstra": 500}})
    assert r.status_code == 200, r.text
    assert r.json()["plan"] == {"strateji": "snowball", "aylik_ekstra": 500.0}
    assert client.patch(f"/api/goals/{gid}", json={"plan": {"strateji": "hizli", "aylik_ekstra": 1}}).status_code == 422
    assert client.patch(f"/api/goals/{gid}", json={"plan": {"strateji": "snowball", "aylik_ekstra": -1}}).status_code == 422


def test_projeksiyon_benimsenen_plani_kullanir(client):
    plansiz = _hedef(client).json()
    planli = _hedef(client, {"strateji": "avalanche", "aylik_ekstra": 20000}).json()
    assert plansiz["projected_completion_date"] and planli["projected_completion_date"]
    assert date.fromisoformat(planli["projected_completion_date"]) < date.fromisoformat(plansiz["projected_completion_date"]), (
        "20.000 TL/ay ekstra ödeme bitişi öne çekmeli — projeksiyon planı okumuyor"
    )


def test_plan_secimi_bozuk_kayda_dayanir():
    g = Goal(goal_type="debt_freedom", title="x", target_amount=Decimal("1"))
    assert plan_secimi(g) == ("snowball", 0.0)
    g.plan = {"strateji": "avalanche", "aylik_ekstra": "abc"}
    assert plan_secimi(g) == ("avalanche", 0.0)
    g.plan = {"strateji": "yok", "aylik_ekstra": -5}
    assert plan_secimi(g) == ("snowball", 0.0)


def test_arayuz_koprusu_tek_kaynak():
    fe = KOK / "frontend" / "src"
    ds = (fe / "panels" / "DebtStrategy.jsx").read_text(encoding="utf-8")
    assert ds.count("onBenimse={() => handleBenimse(") == 2, "iki kartta da benimseme yok"
    assert "planBenimse(" in ds and "goalsApi.create(" not in ds, "yaratma köprüde olmalı, panelde değil"
    kopru = (fe / "lib" / "borcPlani.js").read_text(encoding="utf-8")
    assert "goalsApi.update(mevcut.id" in kopru and "goalsApi.create(" in kopru
    assert "goal_type: 'debt_freedom'" in kopru
    goals = (fe / "panels" / "Goals.jsx").read_text(encoding="utf-8")
    assert "planEtiketi(goal.plan)" in goals, "hedef kartı benimsenen planı göstermiyor"
