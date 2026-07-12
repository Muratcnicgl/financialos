"""
FEAT-030 — satın alma fırsat maliyeti. amount TL'yi harcamak vs en yüksek faizli borca
ödemek → borçsuzluk tarihine + toplam faize etkisi (impuls harcama deterrent, nötr what-if).
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Account, AccountType
from app.debt_strategy import DebtItem, simulate_purchase_opportunity_cost

TODAY = date(2026, 7, 12)


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


def _debts():
    return [
        DebtItem(1, "Kart", "credit_card", 11976, 4.25, 3000),
        DebtItem(2, "K1", "loan", 45000, 2.9, 3800),
        DebtItem(3, "K2", "loan", 28000, 3.1, 2500),
    ]


# ---- pure -------------------------------------------------------------------

def test_borc_yoksa_none(db):
    assert simulate_purchase_opportunity_cost([], 1000, today=TODAY) is None


def test_sifir_tutar_none(db):
    assert simulate_purchase_opportunity_cost(_debts(), 0, today=TODAY) is None


def test_hedef_en_yuksek_faizli_borc(db):
    r = simulate_purchase_opportunity_cost(_debts(), 5000, today=TODAY)
    assert r["hedef_borc"] == "Kart"           # %4.25 en yüksek faiz


def test_odeme_faizi_azaltir_invariant(db):
    """Borca ödemek TOPLAM faizi azaltır (veya eşit) — harcamanın maliyeti negatif değil."""
    r = simulate_purchase_opportunity_cost(_debts(), 8000, today=TODAY)
    assert r["odersen_faiz"] <= r["baseline_faiz"] + 1e-6
    assert r["faiz_tasarrufu"] >= -1e-6        # harcarsan kaybedilen faiz tasarrufu ≥ 0
    assert r["odersen_ay"] <= r["baseline_ay"]  # erken (ya da eşit) biter


def test_tutar_borclara_avalanche_sirasi_tasar(db):
    # 50000 < toplam borç (84976) → tamamı borçlara dağıtılır (kart bitince kredilere taşar)
    r = simulate_purchase_opportunity_cost(_debts(), 50000, today=TODAY)
    assert r["uygulanan"] == 50000.0
    assert r["harcama"] == 50000.0


def test_tutar_toplam_borcu_asarsa_fazlasi_haric(db):
    # 200000 > toplam borç (84976) → yalnız 84976 borca gider (fazlası uygulanmaz)
    r = simulate_purchase_opportunity_cost(_debts(), 200000, today=TODAY)
    assert r["uygulanan"] == pytest.approx(84976.0, abs=0.01)


# ---- endpoint ---------------------------------------------------------------

def test_endpoint_opportunity_cost(client, db):
    db.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card,
                   balance=11976, credit_limit=12000, interest_rate=4.25))
    db.add(Account(user_id=1, name="K1", account_type=AccountType.loan,
                   balance=45000, interest_rate=2.9, monthly_payment=3800, remaining_installments=12))
    db.commit()
    r = client.get("/api/debt-strategy/opportunity-cost?amount=8000")
    assert r.status_code == 200
    body = r.json()
    assert body["hedef_borc"] == "Kart"
    assert body["faiz_tasarrufu"] >= 0


def test_endpoint_borc_yoksa_404(client, db):
    db.add(Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=5000))
    db.commit()
    assert client.get("/api/debt-strategy/opportunity-cost?amount=8000").status_code == 404


def test_endpoint_negatif_tutar_422(client, db):
    assert client.get("/api/debt-strategy/opportunity-cost?amount=-5").status_code == 422
