"""
GET /api/cockpit — frontend'in ANA veri kaynağı. Uçtan uca 200 + anahtar alanlar +
snapshot yazımı (#116 borclar / #117 snapshot receivables doğru).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, PersonalDebt, DebtDirection, NetWorthSnapshot,
)


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_cockpit_200_ve_anahtar_alanlar(client, db_session):
    db_session.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db_session.commit()
    r = client.get("/api/cockpit")
    assert r.status_code == 200
    body = r.json()
    for key in ("nakit_kasa", "kart_borcu", "net_deger", "net_deger_tam", "daily_limit",
                "yarin_limit_harcamasiz", "borclar_toplami", "alacaklar_toplami",
                "upcoming_reminders", "son_islemler", "price_freshness"):
        assert key in body, f"cockpit'te eksik alan: {key}"


def test_cockpit_116_payable_net_degeri_dusor(client, db_session):
    db_session.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db_session.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.payable,
                                amount=1000.0, is_paid=False))
    db_session.commit()
    body = client.get("/api/cockpit").json()
    assert body["borclar_toplami"] == 1000.0
    # net_deger_tam = net_deger + alacak(0) − borç(1000)
    assert abs(body["net_deger_tam"] - (body["net_deger"] - 1000.0)) < 0.01


def test_cockpit_117_snapshot_receivables_saf_alacak(client, db_session):
    """Snapshot'ın receivables alanı SAF alacak olmalı (payable ile karışmamalı)."""
    db_session.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db_session.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                                amount=800.0, is_paid=False))
    db_session.add(PersonalDebt(user_id=1, counterparty="Ali", direction=DebtDirection.payable,
                                amount=1000.0, is_paid=False))
    db_session.commit()
    client.get("/api/cockpit")   # snapshot yazar
    snap = db_session.query(NetWorthSnapshot).filter_by(user_id=1).first()
    assert snap is not None
    # #117: receivables SAF alacak (800), (net_tam − net) = 800−1000 = −200 clamp DEĞİL
    assert float(snap.receivables) == 800.0


def test_cockpit_snapshot_idempotent(client, db_session):
    db_session.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    db_session.commit()
    client.get("/api/cockpit")
    client.get("/api/cockpit")   # ikinci çağrı yeni snapshot yazMAMALI
    assert db_session.query(NetWorthSnapshot).filter_by(user_id=1).count() == 1


def test_cockpit_120_gecikmis_borc_http_uzerinden_alerts(client, db_session):
    """#120 uçtan uca: vadesi geçmiş borç, HTTP cockpit yanıtının alerts'inde görünür
    (JSON serileştirme dahil — numerik 'tutar' alanı round-trip'ten sağ çıkar)."""
    from datetime import date, timedelta
    db_session.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=3000.0))
    db_session.add(PersonalDebt(user_id=1, counterparty="Kirveci", direction=DebtDirection.payable,
                                amount=2500.0, is_paid=False,
                                due_date=date.today() - timedelta(days=4)))
    db_session.commit()

    body = client.get("/api/cockpit").json()
    overdue = [a for a in body["alerts"] if a.get("baslik", "").startswith("Gecikmiş borç")]
    assert len(overdue) == 1
    assert overdue[0]["seviye"] == "kritik"
    assert overdue[0]["tutar"] == 2500.0        # numerik alan JSON'da korundu
    assert body["alerts"][0]["baslik"].startswith("Gecikmiş borç")   # kritik en başta


def test_cockpit_119_yaklasan_alacak_http_uzerinden_reminders(client, db_session):
    """#119 uçtan uca: 0-7 gün içinde vadesi gelen alacak, HTTP cockpit upcoming_reminders'ında."""
    from datetime import date, timedelta
    db_session.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=3000.0))
    db_session.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                                amount=1800.0, is_paid=False,
                                due_date=date.today() + timedelta(days=3)))
    db_session.commit()

    body = client.get("/api/cockpit").json()
    rec = [r for r in body["upcoming_reminders"] if r["type"] == "receivable"]
    assert len(rec) == 1
    assert rec[0]["amount"] == 1800.0
    assert "Efe" in rec[0]["name"]
