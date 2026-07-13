"""
M19 (ADR-031) — /api/prices EVDS endpoint testleri.

get_evds_price mock'lanır (canlı EVDS env-bağımlı). Fiyat varsa 200 + normalize dict;
None (EVDS erişilemez) ise 502 (net mesaj).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.routers.prices as prices_mod

client = TestClient(app)


def test_currency_200(monkeypatch):
    monkeypatch.setattr(prices_mod, "get_evds_price", lambda s: Decimal("34.5000"))
    r = client.get("/api/prices/currency/USD")
    assert r.status_code == 200
    b = r.json()
    assert b["currency"] == "USD" and b["rate"] == "34.5000" and b["source"] == "TCMB_EVDS"


def test_currency_evds_yok_502(monkeypatch):
    monkeypatch.setattr(prices_mod, "get_evds_price", lambda s: None)
    r = client.get("/api/prices/currency/EUR")
    assert r.status_code == 502
    assert "alınamadı" in r.json()["detail"]


def test_gold_200(monkeypatch):
    monkeypatch.setattr(prices_mod, "get_evds_price", lambda s: Decimal("2750.1234"))
    r = client.get("/api/prices/gold/gram")
    assert r.status_code == 200
    assert r.json()["price"] == "2750.1234" and r.json()["type"] == "gram"


def test_gold_evds_yok_502(monkeypatch):
    monkeypatch.setattr(prices_mod, "get_evds_price", lambda s: None)
    r = client.get("/api/prices/gold/gram")
    assert r.status_code == 502


def test_currency_TRY_suffix_eklenmez(monkeypatch):
    seen = {}
    def _cap(s):
        seen["sym"] = s
        return Decimal("1")
    monkeypatch.setattr(prices_mod, "get_evds_price", _cap)
    client.get("/api/prices/currency/USDTRY")
    assert seen["sym"] == "USDTRY"  # zaten TRY ile bitiyorsa tekrar eklenmez
    client.get("/api/prices/currency/GBP")
    assert seen["sym"] == "GBPTRY"
