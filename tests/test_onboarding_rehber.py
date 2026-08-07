"""
P3.3 — BUG #262: ilk kurulum rehberi (`GET/PATCH /api/onboarding/rehber`).

Kapatılan iki defekt:
  (a) Rehber ilk adımdan sonra ORTADAN KAYBOLUYORDU. Kart yalnız `accounts.length === 0`
      iken çiziliyordu; kullanıcı ilk hesabını ekler eklemez kalan üç adım (işlem gir →
      kendi kuralını yaz → koça sor) hiç yönlendirilmiyordu.
  (b) Kartın birincil düğmesi ÖLÜ bir bağlantıydı (`href="#accounts"`); uygulama hash-router
      kullanmıyor. Tarayıcı hata vermez, süit yeşil kalır — sessiz defekt (L28).

Kilitlenen sözleşme:
  1. Adım durumu backend'de deterministik türetilir (tek kaynak; her panel kendi ölçütünü
     uydurmaz — BUG #161/SBN-001 sınıfı).
  2. Rehber TÜM adımlar bitene kadar görünür kalır.
  3. Adımlar YALNIZ kullanıcının KENDİ verisini sayar; demo satırları tamam saymaz.
  4. Gizleme kalıcı ve GERİ ALINABİLİR.
  5. Her adımın `sekme` değeri arayüzde GERÇEKTEN var olan bir sekmedir — ölü CTA kapısı
     (liste elle taşınmaz, `App.jsx`'ten türetilir: L27).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, CoachMemory


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(name="yeni"))
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


def _rehber(client) -> dict:
    r = client.get("/api/onboarding/rehber")
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _tamamlar(d: dict) -> dict:
    return {a["anahtar"]: a["tamam"] for a in d["adimlar"]}


def _kendi_hesabini_ekle(client):
    r = client.post("/api/accounts", json={
        "name": "Vadesiz", "account_type": "cash", "balance": 1000.0})
    assert r.status_code in (200, 201), r.text[:300]
    return r.json()


# ---------------------------------------------------------------- temel durum

def test_yeni_kullanicida_dort_adim_ve_hicbiri_tamam_degil(client):
    d = _rehber(client)
    assert d["toplam"] == 4
    assert d["tamamlanan"] == 0
    assert d["tamamlandi"] is False
    assert d["gorunur"] is True
    assert [a["anahtar"] for a in d["adimlar"]] == ["hesap", "islem", "kural", "koc"]


def test_rehber_ilk_adimdan_sonra_KAYBOLMAZ(client):
    """BUG #262(a) regresyon kapısı — asıl defekt buydu."""
    _kendi_hesabini_ekle(client)
    d = _rehber(client)
    assert _tamamlar(d)["hesap"] is True
    assert d["tamamlanan"] == 1
    assert d["gorunur"] is True, "Rehber ilk adımdan sonra kayboldu (BUG #262 geri geldi)"


# ------------------------------------------------- demo veri tamam saymamalı

def test_demo_veri_hicbir_adimi_tamam_saymaz(client):
    """'Örnek veriyle gez' diyen kullanıcı kendi kurulumuna hiç başlamamıştır.

    Demo satırları sayılsaydı rehber anında 3/4 tamam görünür ve kaybolurdu.
    """
    assert client.post("/api/onboarding/demo").status_code == 201
    d = _rehber(client)
    assert d["tamamlanan"] == 0, f"Demo veri adımları tamam saydı: {_tamamlar(d)}"
    assert d["gorunur"] is True


def test_demo_yukluyken_kendi_verisi_yine_de_sayilir(client):
    client.post("/api/onboarding/demo")
    _kendi_hesabini_ekle(client)
    t = _tamamlar(_rehber(client))
    assert t["hesap"] is True
    assert t["islem"] is False and t["kural"] is False


def test_demo_kaldirilinca_sayim_bozulmaz(client):
    _kendi_hesabini_ekle(client)
    client.post("/api/onboarding/demo")
    client.delete("/api/onboarding/demo")
    d = _rehber(client)
    assert _tamamlar(d)["hesap"] is True
    assert d["tamamlanan"] == 1


# --------------------------------------------------------- adım adım ilerleme

def test_dort_adim_sirayla_tamamlanir_ve_rehber_emekli_olur(client, db):
    hesap = _kendi_hesabini_ekle(client)
    assert _rehber(client)["tamamlanan"] == 1

    r = client.post("/api/transactions", json={
        "account_id": hesap["id"], "transaction_type": "expense",
        "amount": 100.0, "category": "market", "description": "test"})
    assert r.status_code in (200, 201), r.text[:300]
    assert _tamamlar(_rehber(client))["islem"] is True

    r = client.post("/api/checkpoints", json={
        "title": "Nakit tabanı", "description": "Nakit 1000 altına inmesin",
        "checkpoint_type": "red_line", "priority": 2,
        "rule_type": "min_cash_floor", "rule_params": {"amount": 1000}})
    assert r.status_code in (200, 201), r.text[:300]
    assert _tamamlar(_rehber(client))["kural"] is True

    # Koça sormak: geçmişte kullanıcı rolünde bir mesaj olması yeterli.
    db.add(CoachMemory(user_id=db.query(User).first().id, role="user", content="merhaba"))
    db.commit()

    d = _rehber(client)
    assert d["tamamlanan"] == 4
    assert d["tamamlandi"] is True
    assert d["gorunur"] is False, "Tüm adımlar bitti ama rehber hâlâ çiziliyor"


def test_koc_adimi_yalniz_kullanici_mesajiyla_tamam_olur(client, db):
    uid = db.query(User).first().id
    db.add(CoachMemory(user_id=uid, role="assistant", content="karşılama"))
    db.commit()
    assert _tamamlar(_rehber(client))["koc"] is False, \
        "Koçun kendi mesajı 'kullanıcı sordu' sayıldı"


# ------------------------------------------------------------ gizle / göster

def test_gizleme_kalici_ve_geri_alinabilir(client):
    r = client.patch("/api/onboarding/rehber", json={"gizli": True})
    assert r.status_code == 200, r.text[:300]
    assert r.json()["gizli"] is True
    assert r.json()["gorunur"] is False

    assert _rehber(client)["gorunur"] is False        # kalıcı (DB'de)

    r = client.patch("/api/onboarding/rehber", json={"gizli": False})
    assert r.json()["gizli"] is False
    assert r.json()["gorunur"] is True
    assert _rehber(client)["gorunur"] is True         # geri alınabilir


def test_gizli_rehber_adim_durumunu_yine_de_bildirir(client):
    """Gizlemek ölçmeyi durdurmaz — Hesap panelinde '2/4 adım tamam' gösterilebilsin."""
    _kendi_hesabini_ekle(client)
    client.patch("/api/onboarding/rehber", json={"gizli": True})
    d = _rehber(client)
    assert d["tamamlanan"] == 1 and d["gorunur"] is False


# ------------------------------------------- ölü CTA kapısı (BUG #262(b), L27)

_APP_JSX = Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.jsx"


def test_her_adimin_sekmesi_arayuzde_gercekten_var(client):
    """Backend bir sekme adı uydurursa CTA ölü bağlantı olur — kapı burada.

    Sekme listesi ELLE taşınmaz: `App.jsx`'teki `activeTab === '<id>'` dallarından türetilir.
    """
    kaynak = _APP_JSX.read_text(encoding="utf-8")
    gercek = set(re.findall(r"activeTab\s*===\s*'([a-z]+)'", kaynak))
    assert gercek, "App.jsx'ten sekme id'leri okunamadı (kapı ölçmüyor)"

    for adim in _rehber(client)["adimlar"]:
        assert adim["sekme"] in gercek, (
            f"'{adim['anahtar']}' adımı var olmayan '{adim['sekme']}' sekmesine yönlendiriyor "
            f"(mevcut: {sorted(gercek)})")
