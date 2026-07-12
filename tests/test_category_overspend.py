"""
FEAT-005 — kategori bütçe aşım öngörüsü (Copilot/YNAB projected spending).
_category_overspend_alerts: ay-içi harcama hızıyla ay-sonu projeksiyonu geçen ayı belirgin
aşacaksa erken uyarı. Referans: geçen ayın aynı kategori toplamı. Deterministik izole DB.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Transaction, TransactionType
from app.rules_engine import _category_overspend_alerts, generate_cockpit


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


def _exp(db, category, amount, when):
    db.add(Transaction(user_id=1, transaction_type=TransactionType.expense,
                       amount=amount, category=category, transaction_date=when))
    db.commit()


def test_asim_ongorusu_uyari(db):
    # Geçen ay (Nisan) market = 1000. Bu ay (15 Mayıs itibariyle) 800 → projeksiyon
    # 800/15*31 ≈ 1653 > 1000*1.15 → uyarı.
    _exp(db, "market", 1000.0, date(2026, 4, 10))
    _exp(db, "market", 800.0, date(2026, 5, 8))
    alerts = _category_overspend_alerts(1, date(2026, 5, 15), db)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["seviye"] == "uyari"
    assert "market" in a["baslik"]
    assert "geçen ay" in a["mesaj"]
    assert a["tutar"] > 1000.0        # projeksiyon


def test_normal_hiz_uyari_yok(db):
    # Geçen ay 1000; bu ay 15 günde 450 → projeksiyon ~930 < 1150 → uyarı yok
    _exp(db, "market", 1000.0, date(2026, 4, 10))
    _exp(db, "market", 450.0, date(2026, 5, 8))
    assert _category_overspend_alerts(1, date(2026, 5, 15), db) == []


def test_gecen_ay_referansi_yoksa_atlanir(db):
    # Bu ay yeni kategori (geçen ay yok) → kıyas yok → uyarı yok
    _exp(db, "yeni_kategori", 900.0, date(2026, 5, 8))
    assert _category_overspend_alerts(1, date(2026, 5, 15), db) == []


def test_ay_basi_projeksiyon_atlanir(db):
    # < 5 gün → gürültü, projeksiyon yapılmaz
    _exp(db, "market", 1000.0, date(2026, 4, 10))
    _exp(db, "market", 500.0, date(2026, 5, 2))
    assert _category_overspend_alerts(1, date(2026, 5, 3), db) == []


def test_top_n_sinirlar(db):
    # 3 kategori de aşıyor; top_n=2 → sadece 2 uyarı (en yüksek projeksiyon)
    for cat, prev, curr in [("market", 1000, 900), ("yemek", 800, 750), ("eglence", 500, 480)]:
        _exp(db, cat, prev, date(2026, 4, 10))
        _exp(db, cat, curr, date(2026, 5, 8))
    alerts = _category_overspend_alerts(1, date(2026, 5, 15), db)
    assert len(alerts) == 2                      # top_n=2
    # en yüksek projeksiyon (market) önce
    assert "market" in alerts[0]["baslik"]


def test_cockpit_entegrasyonu(db):
    _exp(db, "market", 1000.0, date(2026, 4, 10))
    _exp(db, "market", 800.0, date(2026, 5, 8))
    cockpit = generate_cockpit(1, date(2026, 5, 15), db)
    over = [a for a in cockpit["alerts"] if a.get("baslik", "").startswith("Kategori aşım")]
    assert len(over) == 1
