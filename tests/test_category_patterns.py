"""
_calculate_category_patterns — 30 gün vs önceki 30 gün gider anomali tespiti.
Koça "davranış kalıpları" sinyali (örn. 'yemek %80 arttı') buradan gelir; test edilmemişti.
ANOMALY_THRESHOLD=1.4, PATTERN_MIN_TRANSACTIONS=3. Deterministik izole DB.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Transaction, TransactionType
from app.rules_engine import _calculate_category_patterns

TODAY = date(2026, 6, 1)
CURR = TODAY - timedelta(days=10)   # curr penceresi ([today-29, today]) içinde
PREV = TODAY - timedelta(days=45)   # prev penceresi ([today-59, today-30]) içinde


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


def _exp(db, category, amount, when, n=1):
    for _ in range(n):
        db.add(Transaction(user_id=1, transaction_type=TransactionType.expense,
                           amount=amount, category=category, transaction_date=when))
    db.commit()


def _by_cat(patterns, cat):
    return next((p for p in patterns if p["category"] == cat), None)


def test_anomali_tespiti(db):
    # prev toplam 1000 (2 txn), curr toplam 2000 (3 txn) → +100%, anomali (2000 > 1400)
    _exp(db, "yemek", 500.0, PREV, n=2)
    _exp(db, "yemek", 2000.0 / 3, CURR, n=3)
    p = _by_cat(_calculate_category_patterns(1, TODAY, db), "yemek")
    assert p is not None
    assert p["change_pct"] == 100.0
    assert p["anomaly_flag"] is True


def test_stabil_kategori_anomali_degil(db):
    # prev 1000, curr 1100 (3 txn) → +10%, anomali değil (1100 < 1400)
    _exp(db, "market", 500.0, PREV, n=2)
    _exp(db, "market", 1100.0 / 3, CURR, n=3)
    p = _by_cat(_calculate_category_patterns(1, TODAY, db), "market")
    assert p is not None
    assert p["anomaly_flag"] is False
    assert p["change_pct"] == 10.0


def test_yeni_kategori_change_none_anomali(db):
    # prev 0 (hiç yok), curr 900 (3 txn) → change_pct None, anomali (yeni + curr>0)
    _exp(db, "eglence", 300.0, CURR, n=3)
    p = _by_cat(_calculate_category_patterns(1, TODAY, db), "eglence")
    assert p is not None
    assert p["change_pct"] is None
    assert p["anomaly_flag"] is True


def test_min_islem_altinda_haric(db):
    # curr'da sadece 2 işlem (< 3) → gürültü filtresi ile listeye girmez
    _exp(db, "kirtasiye", 400.0, CURR, n=2)
    assert _by_cat(_calculate_category_patterns(1, TODAY, db), "kirtasiye") is None


def test_muhasebe_kategorisi_haric(db):
    # 'transfer' muhasebe işlemi — patern dışı (3 txn olsa bile)
    _exp(db, "transfer", 1000.0, CURR, n=3)
    assert _by_cat(_calculate_category_patterns(1, TODAY, db), "transfer") is None


def test_gelir_islemleri_sayilmaz(db):
    # income işlemleri gider paternine girmez
    for _ in range(3):
        db.add(Transaction(user_id=1, transaction_type=TransactionType.income,
                           amount=5000.0, category="maas", transaction_date=CURR))
    db.commit()
    assert _by_cat(_calculate_category_patterns(1, TODAY, db), "maas") is None
