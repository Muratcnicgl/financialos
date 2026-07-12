"""
FEAT-001 — kategori bütçe zarfları (envelope budgeting, YNAB/Actual Budget).
calculate_envelopes (bu-ay durum) + CRUD endpoint + FEAT-005 entegrasyonu (zarf = gerçek referans).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Envelope, Transaction, TransactionType
from app.rules_engine import calculate_envelopes, _category_overspend_alerts

TODAY = date(2026, 5, 15)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _exp(db, category, amount, when=TODAY):
    db.add(Transaction(user_id=1, transaction_type=TransactionType.expense,
                       amount=amount, category=category, transaction_date=when))
    db.commit()


def _env(db, category, amount):
    e = Envelope(user_id=1, category=category, monthly_amount=Decimal(str(amount)))
    db.add(e); db.commit(); db.refresh(e)
    return e


# ---- calculate_envelopes ---------------------------------------------------

def test_zarf_yoksa_bos(db):
    r = calculate_envelopes(1, TODAY, db)
    assert r["zarflar"] == [] and r["asan_adet"] == 0


def test_zarf_durumu_harcanan_kalan(db):
    _env(db, "market", 2000)
    _exp(db, "market", 800.0, TODAY - timedelta(days=2))
    _exp(db, "market", 300.0, TODAY - timedelta(days=1))
    r = calculate_envelopes(1, TODAY, db)
    z = r["zarflar"][0]
    assert z["category"] == "market"
    assert z["butce"] == 2000.0
    assert z["harcanan"] == 1100.0
    assert z["kalan"] == 900.0
    assert z["asildi"] is False
    assert r["asan_adet"] == 0


def test_zarf_asimi(db):
    _env(db, "eglence", 500)
    _exp(db, "eglence", 650.0)
    r = calculate_envelopes(1, TODAY, db)
    z = r["zarflar"][0]
    assert z["asildi"] is True
    assert z["kalan"] == -150.0
    assert r["asan_adet"] == 1


def test_gecen_ay_harcamasi_sayilmaz(db):
    _env(db, "market", 1000)
    _exp(db, "market", 900.0, date(2026, 4, 20))   # geçen ay → bu ay zarfına girmez
    r = calculate_envelopes(1, TODAY, db)
    assert r["zarflar"][0]["harcanan"] == 0.0


# ---- FEAT-005 entegrasyonu: zarf gerçek referans olur ----------------------

def test_feat005_zarf_referansi(db):
    # zarf bütçe 300; bu ay 15 günde 250 → projeksiyon ~516 > 300*1.15 → uyarı ("bütçe" referans)
    _env(db, "market", 300)
    _exp(db, "market", 250.0, TODAY - timedelta(days=2))
    alerts = _category_overspend_alerts(1, TODAY, db)
    assert len(alerts) == 1
    assert "bütçe" in alerts[0]["mesaj"]        # geçen ay değil, zarf bütçesi referans
    assert "300" in alerts[0]["mesaj"]


# ---- CRUD endpoint ---------------------------------------------------------

def test_crud_create_list_update_delete(client, db):
    # create
    r = client.post("/api/envelopes", json={"category": "market", "monthly_amount": 1500})
    assert r.status_code == 201
    eid = r.json()["id"]
    # duplicate → 409
    assert client.post("/api/envelopes", json={"category": "market", "monthly_amount": 900}).status_code == 409
    # list (durum dahil)
    body = client.get("/api/envelopes").json()
    assert len(body["envelopes"]) == 1
    assert "durum" in body
    # update
    assert client.put(f"/api/envelopes/{eid}", json={"monthly_amount": 2000}).json()["monthly_amount"] == "2000.00"
    # delete
    assert client.delete(f"/api/envelopes/{eid}").status_code == 204
    assert client.get("/api/envelopes").json()["envelopes"] == []


def test_cockpit_zarflar_alani(db):
    from app.rules_engine import generate_cockpit
    from app.models import Account, AccountType
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=1000.0))
    _env(db, "market", 1000)
    _exp(db, "market", 400.0)
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    assert "zarflar" in c
    assert c["zarflar"]["zarflar"][0]["category"] == "market"


def test_feat002_atanmamis_nakit(db):
    """FEAT-002: atanmamış = nakit - Σ max(0, zarf kalan). market 1000 bütçe, 400 harcanmış
    → kalan 600 taahhüt; nakit 1000 → atanmamış 400."""
    from app.rules_engine import generate_cockpit
    from app.models import Account, AccountType
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=1000.0))
    _env(db, "market", 1000)
    _exp(db, "market", 400.0)
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    assert c["atanmamis_nakit"] == 400.0    # 1000 nakit - 600 zarf taahhüt


def test_feat002_zarf_yoksa_tum_nakit(db):
    from app.rules_engine import generate_cockpit
    from app.models import Account, AccountType
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=5000.0))
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    assert c["atanmamis_nakit"] == 5000.0    # zarf yok → tüm nakit boşta


def test_zarf_koc_contextine_duser(db):
    """FEAT-001/002 koç entegrasyonu: zarf varsa context'te BÜTÇE ZARFLARI + atanmamış nakit."""
    from app.coach import _build_context_message
    from app.models import Account, AccountType
    from datetime import date as _date, timedelta
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=3000.0))
    today = _date.today()
    _env(db, "market", 2000)
    # bu ayın harcaması (context date.today() kullanır)
    db.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=500.0,
                       category="market", transaction_date=today))
    db.commit()
    context, _ = _build_context_message(db, 1)
    assert "BÜTÇE ZARFLARI" in context
    assert "Atanmamış" in context
