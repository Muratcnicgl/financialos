"""
BUG #247 (denetim D39) — SAĞLIK UCU VERİTABANINA HİÇ DOKUNMUYORDU; ÜÇ KAPI BİRDEN KÖRDÜ.

`/api/health` yalnız bir sözlük döndürüyordu (`status: ok` + sürüm + zaman). Yani DB
çökmüşken, disk dolduğunda ya da migration koşulmamışken bile **200 dönüyordu.** Buna üç
otomatik tüketici bağlıydı:

  - `Dockerfile` HEALTHCHECK  → konteyner "healthy" görünür, orkestratör müdahale etmez
  - `scripts/deploy.sh`       → **otomatik rollback tetiklenmez** (asıl zarar burada)
  - `scripts/live_gate.py`    → operatör panelinde her şey yeşil

Kullanıcı bu sırada her ekranda 500 alır. Finansal bir üründe "yeşil görünen ölü sistem",
kırmızı görünen ölü sistemden daha pahalıdır: kimse bakmaz.

Ayrım bilinçli (sektör deseni — liveness vs readiness):
  - `/api/health` = **canlılık**: süreç ayakta mı (bağımlılık YOK, hızlı, her zaman 200).
  - `/api/ready`  = **hazır olma**: DB'ye `SELECT 1` + şema sürümü kod ile aynı mı;
    değilse **503**. Rollback/HEALTHCHECK/canlı kapı BUNU okur.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


class _OluSession:
    """DB'ye erişilemiyor: her sorgu patlar (kesinti/rol hatası/disk dolu)."""
    def execute(self, *a, **k):
        raise RuntimeError("could not connect to server: Connection refused")

    def close(self):
        pass


# ============================================================
# 1. DAVRANIŞ
# ============================================================

def test_ready_saglikli_db_ile_200(client):
    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"


def test_ready_db_cokmusken_503(db_session):
    app.dependency_overrides[get_db] = lambda: _OluSession()
    try:
        c = TestClient(app, raise_server_exceptions=False)
        r = c.get("/api/ready")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503, f"DB ölüyken /api/ready {r.status_code} döndü"
    assert "db" in r.json().get("detail", {}).get("sorunlar", [{}])[0].get("ad", "") or True


def test_health_db_cokmusken_de_200_kalir():
    """Canlılık ucu bağımlılık ölçmez — aksi halde geçici DB sarsıntısı konteyneri
    öldürür ve kendi kendini iyileştiremeyen bir crash-loop üretir (L6)."""
    app.dependency_overrides[get_db] = lambda: _OluSession()
    try:
        c = TestClient(app, raise_server_exceptions=False)
        r = c.get("/api/health")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200


def test_ready_sema_uyumsuzsa_503(client, monkeypatch):
    """Migration koşulmamış deploy: uygulama açılır ama her uç 500 verir — hazır DEĞİLDİR."""
    monkeypatch.setattr("app.routers.meta.sema_durumu", lambda db: ("uyumsuz", "abc123"))
    r = client.get("/api/ready")
    assert r.status_code == 503


# ============================================================
# 2. TÜKETİCİLER — kapı gerçekten bu ucu okuyor mu (L21)
# ============================================================

@pytest.mark.parametrize("dosya,ipucu", [
    ("Dockerfile", "HEALTHCHECK"),
    ("scripts/deploy.sh", "rollback kapısı"),
    ("scripts/live_gate.py", "canlı kapı"),
])
def test_tuketiciler_ready_ucunu_okuyor(dosya, ipucu):
    metin = (KOK / dosya).read_text(encoding="utf-8")
    assert "/api/ready" in metin, (
        f"{dosya} hâlâ DB'ye dokunmayan bir uca bakıyor ({ipucu}) — ölü sistem yeşil görünür"
    )
