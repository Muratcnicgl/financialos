"""
API-002 / BUG #389 KAPISI — accounts/debts LİSTELERİ SINIRSIZDI.

Ölçülen (11 Eyl 2026): `GET /api/transactions` BUG #154 ile `limit` (200, ≤1000) almıştı;
`GET /api/accounts` ve `GET /api/debts` `.all()` dönüyordu. Tek kullanıcıda onlarca satır
(canlı: hesap 10'un altında) — bugün sorun değil, ama "veri büyüdükçe" iddiası kodla değil
kullanıcı davranışıyla sınırlıydı. Aynı desen kopyalandı: `limit` (500, 1..1000).

Kapı: sınırın ÜSTÜNDE satır varken yanıt sınırda kalır; `le` aşılırsa 422; varsayılan
küçük listeleri etkilemez (frontend limit göndermez).
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
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="u")); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        yield s, TestClient(app)
    finally:
        app.dependency_overrides.clear(); s.close()


def test_accounts_varsayilan_sinir_ve_ust_tavan(ortam):
    s, c = ortam
    s.add_all(Account(user_id=1, name=f"h{i}", account_type=AccountType.cash, balance=1) for i in range(503))
    s.commit()
    assert len(c.get("/api/accounts").json()) == 500
    assert len(c.get("/api/accounts?limit=7").json()) == 7
    assert len(c.get("/api/accounts?limit=1000").json()) == 503
    assert c.get("/api/accounts?limit=1001").status_code == 422
    assert c.get("/api/accounts?limit=0").status_code == 422


def test_debts_varsayilan_sinir_ve_ust_tavan(ortam):
    s, c = ortam
    s.add_all(PersonalDebt(user_id=1, counterparty=f"k{i}", direction="receivable", amount=1) for i in range(502))
    s.commit()
    assert len(c.get("/api/debts").json()) == 500
    assert len(c.get("/api/debts?limit=3").json()) == 3
    assert c.get("/api/debts?limit=1001").status_code == 422
