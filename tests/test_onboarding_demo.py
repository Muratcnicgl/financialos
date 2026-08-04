"""
P3.5 / H5 (Wave-9) — BUG #194: isteğe bağlı demo veri + TAM silinebilirlik.

Yeni kullanıcı bomboş ekranla karşılaşıyordu; tek "örnek veri" yolu
`scripts/setup_data.py`'ydi — o da BAŞKASININ kanonik verisini yükler ve `drop_all`
yapar (bir beta kullanıcısına asla bulaşmamalı).

Kilitlenen sözleşme:
  1. Demo veri OTOMATİK yüklenmez (kayıt boş başlar — P3.5 e2e ile birlikte).
  2. Yüklenince kullanıcı gerçek bir tablo görür (hesap/işlem/gelir/hedef/kural).
  3. Kaldırılınca **hiç iz kalmaz**.
  4. **Kullanıcının KENDİ verisi asla silinmez** (yalnız işaretli satırlar).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Account, Transaction, DemoDataMarker


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    u = User(name="yeni")
    s.add(u)
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.query(User).first()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_baslangicta_demo_yuklu_degil(client):
    r = client.get("/api/onboarding/demo")
    assert r.status_code == 200
    assert r.json()["yuklu"] is False


def test_demo_yuklenince_gercek_veri_gorunur(client, db):
    r = client.post("/api/onboarding/demo")
    assert r.status_code == 201, r.text[:300]
    assert r.json()["yuklu"] is True

    assert client.get("/api/accounts").json(), "Demo sonrası hesap yok"
    assert client.get("/api/transactions").json(), "Demo sonrası işlem yok"
    assert client.get("/api/checkpoints").json(), "Demo sonrası kural yok"
    assert client.get("/api/cockpit").json()["nakit_kasa"] > 0


def test_demo_kaldirilinca_iz_kalmaz(client, db):
    client.post("/api/onboarding/demo")
    r = client.delete("/api/onboarding/demo")
    assert r.status_code == 200
    assert r.json()["yuklu"] is False

    assert client.get("/api/accounts").json() == []
    assert client.get("/api/transactions").json() == []
    assert client.get("/api/checkpoints").json() == []
    assert db.query(DemoDataMarker).count() == 0


def test_kullanicinin_kendi_verisi_silinmez(client, db):
    """En kritik güvence: demo kaldırma, kullanıcının GERÇEK verisine dokunmaz."""
    client.post("/api/accounts", json={
        "name": "Benim Gerçek Hesabım", "account_type": "cash", "balance": 7777.0})
    client.post("/api/onboarding/demo")
    client.delete("/api/onboarding/demo")

    hesaplar = client.get("/api/accounts").json()
    assert len(hesaplar) == 1, f"Kullanıcının kendi verisi etkilendi: {hesaplar}"
    assert hesaplar[0]["name"] == "Benim Gerçek Hesabım"
    assert hesaplar[0]["balance"] == pytest.approx(7777.0)


def test_iki_kez_yuklenemez(client):
    assert client.post("/api/onboarding/demo").status_code == 201
    assert client.post("/api/onboarding/demo").status_code == 409


def test_demo_veride_kisiye_ozel_iz_yok(client, db):
    """BUG #166/#168 ailesi: demo veri jenerik olmalı (kişi adı / banka markası yok)."""
    client.post("/api/onboarding/demo")
    metinler = []
    for a in db.query(Account).all():
        metinler += [a.name or "", a.notes or ""]
    for t in db.query(Transaction).all():
        metinler += [t.description or "", t.category or ""]
    birlesik = " ".join(metinler).lower()
    for yasak in ("murat", "efe", "rezan", "enpara", "ziraat", "garanti"):
        assert yasak not in birlesik, f"Demo veride kişiye özel iz: {yasak}"


def test_demo_kurali_gercekten_dayatilir(client, db):
    """Demo kural da yapılandırılmış olmalı — 'örnek' diye sahte olmamalı."""
    client.post("/api/onboarding/demo")
    kurallar = client.get("/api/checkpoints").json()
    yapilandirilmis = [k for k in kurallar if k.get("rule_type")]
    assert yapilandirilmis, "Demo kural yapılandırılmamış (yalnız metin)"
    assert yapilandirilmis[0]["rule_params"]["amount"] > 0
