"""
OBS-018 + OBS-009 (BUG #493): veritabanı sağlığı ve iş süreleri ÖLÇÜLÜR.

Ölçüm (14 Eyl 2026): SQLite dosya/WAL boyutu, büyüyen tabloların satırı ve "database is
locked" olup olmadığı hiçbir uçtan okunamıyordu; scheduler kayıtları başlangıç/bitiş
taşıyordu ama süre hiçbir yerde görünmüyordu (yavaşlayan gece işi fark edilmezdi).
Kilitlenen:
  1. `/api/ops/db` dosya DB'de boyutu, satır sayılarını (gerçek COUNT) ve sayacı döner,
  2. kilit hatası sayacı yalnız "database is locked" için artar (başka hata saymaz),
  3. `/api/ops/scheduler` her iş için son süre ve son-10 ortalamasını verir,
  4. uç kimlik ister (ops ailesi).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database as _db
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Base, SchedulerRun, Transaction, TransactionType, User


@pytest.fixture
def dosya_db(tmp_path):
    yol = tmp_path / "saglik.db"
    eng = create_engine(f"sqlite:///{yol.as_posix()}")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="t"))
    s.add_all([Transaction(user_id=1, transaction_type=TransactionType.expense, amount=10 + i, category="x") for i in range(7)])
    t0 = datetime(2026, 9, 14, 3, 0, 0)
    s.add_all([
        SchedulerRun(job_name="nightly_batch", started_at=t0, finished_at=t0 + timedelta(seconds=12), ok=True, detail=""),
        SchedulerRun(job_name="nightly_batch", started_at=t0 + timedelta(days=1), finished_at=t0 + timedelta(days=1, seconds=30), ok=True, detail=""),
    ])
    s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        yield s, yol
    finally:
        app.dependency_overrides.clear()
        s.close()
        eng.dispose()


def test_db_ucu_boyut_satir_ve_sayac(dosya_db):
    s, yol = dosya_db
    r = TestClient(app).get("/api/ops/db")
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["motor"] == "sqlite"
    assert g["dosya_mb"] is not None and g["dosya_mb"] > 0
    satirlar = {t["ad"]: t["satir"] for t in g["tablolar"]}
    assert satirlar["transactions"] == 7
    assert satirlar["scheduler_runs"] == 2
    assert g["toplam_satir"] == sum(satirlar.values())
    assert g["tablolar"][0]["satir"] >= g["tablolar"][-1]["satir"]   # azalan
    assert isinstance(g["kilit_hatasi_sayisi"], int)


def test_kilit_sayaci_yalniz_kilit_hatasinda_artar():
    onceki = _db.KILIT_HATASI["sayi"]
    _db._kilit_hatasini_say(SimpleNamespace(original_exception=Exception("no such table: x")))
    assert _db.KILIT_HATASI["sayi"] == onceki
    _db._kilit_hatasini_say(SimpleNamespace(original_exception=Exception("(sqlite3.OperationalError) database is locked")))
    assert _db.KILIT_HATASI["sayi"] == onceki + 1
    assert _db.KILIT_HATASI["son"] is not None


def test_scheduler_ucu_sure_verir(dosya_db):
    r = TestClient(app).get("/api/ops/scheduler")
    assert r.status_code == 200, r.text
    is_ = next(i for i in r.json()["isler"] if i["job_name"] == "nightly_batch")
    assert is_["son_sure_sn"] == 30.0
    assert is_["ortalama_sure_sn"] == 21.0


def test_db_ucu_kimlik_ister():
    app.dependency_overrides.clear()
    r = TestClient(app).get("/api/ops/db")
    assert r.status_code in (401, 404)
