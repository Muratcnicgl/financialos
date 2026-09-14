"""
API-017 (BUG #492): hız sınırı bilgisi standart başlıklarla döner.

Ölçüm (14 Eyl 2026): 429 yalnız gövde metniyle geliyordu; istemci ne kadar bekleyeceğini
bilmiyordu (`Retry-After` yok), sınırlı uçlarda kalan hak görünmüyordu. Kilitlenen:
  1. sınırlı uçta her yanıt `X-RateLimit-Limit/Remaining/Reset` taşır, Remaining her istekte düşer,
  2. aşımda 429 + `Retry-After` (pencere saniyesi) + `X-RateLimit-Remaining: 0`,
  3. sınırsız uç (sağlık) bu başlıkları TAŞIMAZ (yanlış vaat olmaz).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import rate_limit
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Base, User


@pytest.fixture
def client():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="t")); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    rate_limit.reset()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        rate_limit.reset()
        s.close()


def test_sinirli_ucta_basliklar_ve_dusen_kalan(client):
    max_r, pencere = rate_limit.limit_for("actions")
    r1 = client.post("/api/actions/99999/reject", json={})
    r2 = client.post("/api/actions/99999/reject", json={})
    assert r1.headers["X-RateLimit-Limit"] == str(max_r)
    assert r1.headers["X-RateLimit-Reset"] == str(pencere)
    assert int(r1.headers["X-RateLimit-Remaining"]) == max_r - 1
    assert int(r2.headers["X-RateLimit-Remaining"]) == max_r - 2


def test_asimda_429_retry_after(client):
    max_r, pencere = rate_limit.limit_for("actions")
    for _ in range(max_r):
        client.post("/api/actions/99999/reject", json={})
    r = client.post("/api/actions/99999/reject", json={})
    assert r.status_code == 429
    assert r.headers["Retry-After"] == str(pencere)
    assert r.headers["X-RateLimit-Remaining"] == "0"
    assert r.headers["X-RateLimit-Limit"] == str(max_r)


def test_sinirsiz_uc_baslik_tasimaz(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "X-RateLimit-Limit" not in r.headers
