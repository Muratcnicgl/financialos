"""
P5.3 (Wave-9) — BUG #203: "cron çalıştı mı?" sorusunun cevabı YOKTU.

Zamanlanmış işler yalnızca log dosyasına yazıyordu. Operatör (tek kişi), fiyat cron'unun
gece çalışıp çalışmadığını ancak konteyner log'unu okuyarak anlayabiliyordu. Bir iş
sessizce ölürse — scheduler servisi ayakta ama job patlıyor — bu HAFTALARCA fark edilmez:
fiyatlar bayatlar, gece batch'i insight üretmez, kullanıcı yanlış rakamlara bakar.

Kilitlenen sözleşme: her çalışma kaydedilir (başarı/başarısızlık dahil), izleme işi
ASLA düşürmez, tablo şişmez ve durum kimlikli bir uçtan okunabilir.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.scheduler as sched
from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, SchedulerRun


@pytest.fixture
def db(monkeypatch):
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    s = Session()
    s.add(User(name="operator"))
    s.commit()
    monkeypatch.setattr(sched, "SessionLocal", Session)
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.query(User).first()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_calisma_kaydi_acilir_ve_kapanir(db):
    kid = sched._kayit_basla("test_job")
    assert kid is not None
    sched._kayit_bitir(kid, True, "3/3 hesap")
    k = db.query(SchedulerRun).filter(SchedulerRun.id == kid).first()
    assert k.ok is True and k.finished_at is not None and "3/3" in k.detail


def test_basarisiz_is_sessizce_kaybolmaz(db):
    kid = sched._kayit_basla("kirik_job")
    sched._kayit_bitir(kid, False, "ConnectionError")
    k = db.query(SchedulerRun).filter(SchedulerRun.id == kid).first()
    assert k.ok is False and k.detail == "ConnectionError"


def test_izleme_isi_dusurmez(monkeypatch):
    """DB erişilemezse bile job akışı devam etmeli — izleme İKİNCİLDİR."""
    def patla():
        raise RuntimeError("db yok")
    monkeypatch.setattr(sched, "SessionLocal", patla)
    assert sched._kayit_basla("x") is None      # exception SIZMAMALI
    sched._kayit_bitir(None, True)              # None ile çağrı güvenli


def test_tablo_sismez(db):
    """İş başına son 50 kayıt yeter; aksi halde tablo sınırsız büyür."""
    for i in range(60):
        kid = sched._kayit_basla("cok_kosan")
        sched._kayit_bitir(kid, True, f"kosum {i}")
    n = db.query(SchedulerRun).filter(SchedulerRun.job_name == "cok_kosan").count()
    assert n <= 51, f"Eski kayıtlar temizlenmiyor ({n})"


def test_ops_ucu_durumu_doner(client, db):
    kid = sched._kayit_basla("fetch_investment_prices")
    sched._kayit_bitir(kid, True, "2/2")
    r = client.get("/api/ops/scheduler")
    assert r.status_code == 200
    body = r.json()
    isler = {i["job_name"]: i for i in body["isler"]}
    assert "fetch_investment_prices" in isler
    assert isler["fetch_investment_prices"]["son_sonuc"] is True
    assert isler["fetch_investment_prices"]["saat_once"] is not None


def test_hic_calisma_yoksa_acikca_soyler(client):
    """Sessiz boş liste 'her şey yolunda' sanılmasın."""
    r = client.get("/api/ops/scheduler")
    assert r.json()["hic_calisma_yok"] is True


def test_ops_ucu_kimliksiz_erisime_kapali(db, monkeypatch):
    """İş adları/hata tipleri operasyon bilgisidir — herkese açılmaz."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret-ops-visibility-0123456789ab")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides.pop(get_current_user, None)
    try:
        c = TestClient(app)
        assert c.get("/api/ops/scheduler").status_code == 401
    finally:
        app.dependency_overrides.clear()
