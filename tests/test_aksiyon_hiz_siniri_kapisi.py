"""
SEC-004 / BUG #382 KAPISI — approve/reject/edit UÇLARININ HIZ SINIRI YOKTU.

Ölçülen (11 Eyl 2026): `rate_limit` yetki uçları, davet ve fiyat uçlarında vardı;
koç/chat günlük kota + eşzamanlılık tavanıyla korunuyordu. `/api/actions/{id}/approve`,
`/reject`, `/edit` ise sınırsızdı — kimlik zorunlu (yabancı DoS değil), ama tek bir oturum
ya da çalınmış bir token saniyede yüzlerce onay/redle DB'yi ve reflection arka planını
doldurabilirdi (OWASP API4:2023). Backlog 60+ gündür "kısmen".

Kilitlenen: `actions` kovası (60/dk, istemci IP'si başına), üç uçta da, kimlik/varlık
kontrolünden ÖNCE (yani 404 dönecek istek de sayılır — kova bir tahmin oyunu için de
kapı olmalı).
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
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat")); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    rate_limit.reset()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        rate_limit.reset()
        s.close()


def test_kova_tanimli_ve_makul():
    max_r, window = rate_limit.limit_for("actions")
    assert (max_r, window) == (60, 60), "actions kovası beklenen tavanda değil"


@pytest.mark.parametrize("uc", ["approve", "reject", "edit"])
def test_altmis_birinci_istek_429(client, uc):
    """İlk 60 istek kovayı doldurur (404 döner — aksiyon yok ama SAYILIR), 61. → 429."""
    max_r, _ = rate_limit.limit_for("actions")
    govde = {"payload": {"amount": 1}, "summary": "x"} if uc == "edit" else {}
    kodlar = [client.post(f"/api/actions/99999/{uc}", json=govde).status_code for _ in range(max_r)]
    assert 429 not in kodlar, f"tavan dolmadan 429 döndü: {kodlar}"
    assert client.post(f"/api/actions/99999/{uc}", json=govde).status_code == 429, (
        f"{uc}: {max_r + 1}. istek 429 dönmedi — hız sınırı bağlı değil"
    )
