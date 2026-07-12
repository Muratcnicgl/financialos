"""
SEC-032 — finansal sayısal alan doğrulaması. inf/NaN/taşma (1e308) değerleri GİRİŞTE
reddedilmeli; aksi halde rules_engine matematiğine sızıp round(inf)/taşma çökmelerine yol
açarlar (sağlık skoru round(inf) bug sınıfı — savunma girişe de konur).

İki katman:
- ŞEMA (unit): inf/NaN Pydantic tipinde reddedilir (asıl invariant; tarayıcı JSON'u zaten
  Infinity/NaN taşıyamaz — JSON.stringify(Infinity)=="null" — bu yüzden HTTP katmanında değil
  şema seviyesinde doğruluyoruz).
- HTTP: taşma değeri (1e308, geçerli JSON — yazım hatası/bozuk içe-aktarımın gerçek yolu) 422;
  meşru büyük sonlu değer kabul; işaret kontrolü korunur.
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Account, AccountType
from app.routers.accounts import AccountCreate
from app.routers.debts import DebtCreate
from app.routers.incomes import IncomeCreate


# ---- ŞEMA seviyesi: inf/NaN reddedilir --------------------------------------

@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan"), 1e308])
def test_hesap_bakiye_non_finite_sema_reddeder(bad):
    with pytest.raises(ValidationError):
        AccountCreate(name="X", account_type="cash", balance=bad)


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), 1e308])
def test_hesap_limit_non_finite_sema_reddeder(bad):
    with pytest.raises(ValidationError):
        AccountCreate(name="K", account_type="credit_card", balance=100, credit_limit=bad)


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), 1e308, -5, 0])
def test_borc_tutari_gecersiz_sema_reddeder(bad):
    with pytest.raises(ValidationError):
        DebtCreate(counterparty="Efe", direction="receivable", amount=bad)


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), 1e308, -1, 0])
def test_gelir_tutari_gecersiz_sema_reddeder(bad):
    with pytest.raises(ValidationError):
        IncomeCreate(name="Maas", amount=bad, day_of_month=15)


def test_mesru_deger_sema_kabul_eder():
    a = AccountCreate(name="Z", account_type="cash", balance=-1500.0)  # nakit negatif de olabilir
    assert a.balance == -1500.0
    d = DebtCreate(counterparty="Efe", direction="receivable", amount=999999.0)
    assert d.amount == 999999.0


# ---- HTTP seviyesi: taşma / işaret / meşru büyük -----------------------------

@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(id=1, user_id=1, name="Nakit", account_type=AccountType.cash, balance=5000))
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


def test_http_tasma_degeri_422(client):
    """1e308 geçerli JSON sayısı (yazım hatası yolu) ama üst sınırı aşar → 422."""
    r = client.post("/api/accounts", content='{"name":"X","account_type":"cash","balance":1e308}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422, r.text


def test_http_mesru_buyuk_deger_kabul(client):
    r = client.post("/api/accounts", json={"name": "Zengin", "account_type": "cash", "balance": 1000000.0})
    assert r.status_code in (200, 201), r.text
    assert math.isfinite(r.json()["balance"])


def test_http_islem_negatif_dostca_reddedilir(client):
    """İşlem ≤0 kontrolü handler'daki dostça mesajı korur (SEC-032 sonrası da)."""
    r = client.post("/api/transactions",
                    json={"transaction_type": "expense", "amount": -200, "account_id": 1})
    assert r.status_code in (400, 422)
