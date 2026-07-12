"""
Uçtan-uca kullanıcı yolculuğu — tüm yeni yüzeyin birlikte çalıştığını doğrular (entegrasyon).
Kurulum → cockpit (tüm metrikler) → bütçe → abonelik → raporlar → export. Birim testlerin
kaçırdığı entegrasyon kırıklıklarını yakalar.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, Transaction, TransactionType, RecurringIncome,
    PersonalDebt, DebtDirection,
)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    # Murat benzeri manzara
    s.add(User(id=1, name="Murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    s.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                  balance=11976.0, credit_limit=12000.0, interest_rate=4.0,
                  statement_day=2, payment_day=12))
    s.add(Account(user_id=1, name="Kredi1", account_type=AccountType.loan, balance=30000.0,
                  monthly_payment=5000.0, remaining_installments=6, interest_rate=2.5,
                  next_payment_date=date.today() + timedelta(days=5)))
    s.add(RecurringIncome(user_id=1, name="KYK", amount=4000.0, day_of_month=8, is_active=True))
    s.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                       amount=8000.0, is_paid=False, due_date=date.today() + timedelta(days=3)))
    for i in range(3):
        s.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=59.99,
                          category="abonelik", description="Netflix",
                          transaction_date=date.today() - timedelta(days=70 - i * 30)))
    for i in range(6):
        s.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=150.0,
                          category="market", transaction_date=date.today() - timedelta(days=i * 2)))
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


def test_tam_yolculuk_tum_yuzey_calisir(client):
    # 1. Cockpit — tüm yeni metrikler mevcut ve tutarlı
    c = client.get("/api/cockpit")
    assert c.status_code == 200
    body = c.json()
    for key in ("saglik_skoru", "faiz_sizintisi", "guvenli_harcama", "nakit_runway_gun",
                "zarflar", "atanmamis_nakit", "borc_ozgurluk", "abonelik_yuku", "alerts"):
        assert key in body, f"cockpit'te eksik: {key}"
    assert 0 <= body["saglik_skoru"]["skor"] <= 100
    assert body["faiz_sizintisi"]["aylik_toplam"] > 0          # kart+kredi faizi

    # 2. Bütçe: zarf oluştur → cockpit yansıtır
    assert client.post("/api/envelopes", json={"category": "market", "monthly_amount": 2000}).status_code == 201
    env = client.get("/api/envelopes").json()
    assert env["durum"]["zarflar"][0]["category"] == "market"
    assert "atanmamis_nakit" in env

    # 3. Abonelik: tespit + düzenli gidere çevir
    subs = client.get("/api/subscriptions").json()
    assert subs["adet"] >= 1
    r = client.post("/api/subscriptions/to-recurring", json={
        "isim": "Netflix", "aylik_tutar": 59.99, "account_id": 1, "day_of_month": 15})
    assert r.status_code == 201

    # 4. Raporlar: attribution + real (yeterli geçmiş yok → available:false, ama 200)
    assert client.get("/api/reports/net-worth-attribution").status_code == 200
    assert client.get("/api/reports/real-net-worth").status_code == 200
    assert client.get("/api/reports/monthly-summary").status_code == 200

    # 5. Veri egemenliği: export tüm veriyi döner
    exp = client.get("/api/user/export").json()
    assert exp["schema"] == "financialos-export-v1"
    assert len(exp["accounts"]) == 3
    assert len(exp["transactions"]) >= 9
    assert len(exp["envelopes"]) == 1
