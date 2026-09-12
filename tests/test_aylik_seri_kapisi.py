"""
DVIZ-004 / FEAT-023 / BUG #428 KAPISI — ÇOK-AYLI GELİR/GİDER/TASARRUF SERİSİ.

Ölçülen (12 Eyl 2026): aylık özet (A3) tek ay + önceki ay trendi veriyordu; ay-be-ay seri
ve tasarruf oranının zaman içindeki seyri yoktu. `generate_monthly_series` aynı
`_month_aggregates` kaynağından N ayı üretir — aylık özetle sayılar birebir.

Kilitlenen: seri eskiden yeniye, N ay, yıl geçişi doğru; her ayın sayıları aylık özetle
aynı; gelirsiz ayda savings_rate None (sıfır değil); ortalama yalnız dolu aylardan; uç
korumalı ve `months` sınırlı.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Account, AccountType, Base, Transaction, TransactionType, User
from app.rules_engine import generate_monthly_series, generate_monthly_summary


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)(); ses.add(User(id=1, name="u")); ses.commit()
    acc = Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=0); ses.add(acc); ses.commit()
    def tx(d, tip, tutar):
        ses.add(Transaction(user_id=1, account_id=acc.id, transaction_type=tip, amount=tutar, transaction_date=d, category="x"))
    tx(date(2026, 1, 10), TransactionType.income, 1000); tx(date(2026, 1, 12), TransactionType.expense, 400)   # Oca: %60
    tx(date(2025, 12, 5), TransactionType.income, 2000); tx(date(2025, 12, 6), TransactionType.expense, 1500)  # Ara: %25
    tx(date(2025, 11, 5), TransactionType.expense, 300)                                                          # Kas: gelir yok
    ses.commit()
    yield ses; ses.close()


def test_seri_sirali_yil_gecisli_ve_ozetle_ayni(s):
    r = generate_monthly_series(1, 2026, 1, s, ay_sayisi=3)
    assert [(x["year"], x["month"]) for x in r["series"]] == [(2025, 11), (2025, 12), (2026, 1)]
    oca = r["series"][-1]
    assert (oca["total_income"], oca["total_expense"], oca["net_change"], oca["savings_rate"]) == (1000, 400, 600, 60.0)
    ozet = generate_monthly_summary(1, 2025, 12, s)["current"]
    ara = r["series"][1]
    assert (ara["total_income"], ara["total_expense"]) == (ozet["total_income"], ozet["total_expense"])
    assert r["series"][0]["savings_rate"] is None, "gelirsiz ay: oran bilinmez, 0 değil"
    assert r["avg_savings_rate"] == 42.5   # (60 + 25) / 2 — None dışarıda


def test_uc_korumali_ve_sinirli(s):
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        c = TestClient(app)
        r = c.get("/api/reports/monthly-series?months=3")
        assert r.status_code == 200 and r.json()["months"] == 3 and len(r.json()["series"]) == 3
        assert c.get("/api/reports/monthly-series?months=25").status_code == 422
    finally:
        app.dependency_overrides.clear()
