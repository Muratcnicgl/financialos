"""
API-009 / BUG #410 KAPISI — KISMİ GÜNCELLEME PATCH İLE, TEK ALAN GÖNDERMEK YETER.

Ölçülen (12 Eyl 2026): accounts/debts PUT işleyicileri zaten `model_dump(exclude_unset=True)`
ile kısmi güncelleme yapıyordu (tüm alanlar Optional); madde "PUT ile tam-nesne zorunlu"
derken yanlıştı — eksik olan fiil ve sözleşmeydi: istemci kısmi gövdeyi PUT'a gönderiyordu.
PATCH aynı işleyiciye bağlandı; PUT geriye uyum için kalır.

Kilitlenen: PATCH tek alanı değiştirir, diğerlerine DOKUNMAZ; PUT aynı davranır;
gönderilmeyen alan None'a EZİLMEZ.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Account, AccountType, Base, PersonalDebt, User


@pytest.fixture
def ortam():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)(); s.add(User(id=1, name="u")); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        yield s, TestClient(app)
    finally:
        app.dependency_overrides.clear(); s.close()


@pytest.mark.parametrize("fiil", ["patch", "put"])
def test_hesap_tek_alan_digerine_dokunmaz(ortam, fiil):
    s, c = ortam
    a = Account(user_id=1, name="Kumbara", account_type=AccountType.cash, balance=500, notes="not")
    s.add(a); s.commit()
    r = getattr(c, fiil)(f"/api/accounts/{a.id}", json={"name": "Yeni ad"})
    assert r.status_code == 200, r.text
    s.refresh(a)
    assert (a.name, float(a.balance), a.notes) == ("Yeni ad", 500.0, "not")


@pytest.mark.parametrize("fiil", ["patch", "put"])
def test_borc_tek_alan_digerine_dokunmaz(ortam, fiil):
    s, c = ortam
    d = PersonalDebt(user_id=1, counterparty="Ahmet", direction="receivable", amount=100, description="açıklama")
    s.add(d); s.commit()
    r = getattr(c, fiil)(f"/api/debts/{d.id}", json={"amount": 250})
    assert r.status_code == 200, r.text
    s.refresh(d)
    assert (d.counterparty, float(d.amount), d.description) == ("Ahmet", 250.0, "açıklama")
