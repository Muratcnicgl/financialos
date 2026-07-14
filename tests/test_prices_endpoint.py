"""
M19-v3 (ADR-029 revize) — /api/prices EVDS v3 endpoint testleri.

fetch_currency_rate/fetch_gold_price mock'lanır (canlı EVDS env-bağımlı). Döviz alış+satış
200; None → 502. Tarih formatı 422.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.routers.prices as prices_mod

client = TestClient(app)


def test_currency_200_buy_sell(monkeypatch):
    monkeypatch.setattr(prices_mod, "fetch_currency_rate",
                        lambda code, target=None: {"buy": Decimal("46.9121"), "sell": Decimal("46.9966"),
                                                   "date": "14-07-2026", "source": "TCMB_EVDS_v3"})
    r = client.get("/api/prices/currency/USD")
    assert r.status_code == 200
    b = r.json()
    assert b["currency"] == "USD" and b["rate_buy"] == "46.9121" and b["rate_sell"] == "46.9966"
    assert b["source"] == "TCMB_EVDS_v3" and b["date"] == "14-07-2026"


def test_currency_evds_yok_502(monkeypatch):
    monkeypatch.setattr(prices_mod, "fetch_currency_rate", lambda code, target=None: None)
    r = client.get("/api/prices/currency/EUR")
    assert r.status_code == 502
    assert "alınamadı" in r.json()["detail"]


def test_currency_bos_deger_502(monkeypatch):
    monkeypatch.setattr(prices_mod, "fetch_currency_rate",
                        lambda code, target=None: {"buy": None, "sell": None, "date": "x", "source": "x"})
    assert client.get("/api/prices/currency/GBP").status_code == 502


def test_gold_200(monkeypatch):
    monkeypatch.setattr(prices_mod, "fetch_gold_price",
                        lambda t, target=None: {"price": Decimal("73804.1900"), "date": "10-07-2026",
                                                "source": "TCMB_EVDS_v3"})
    r = client.get("/api/prices/gold/bilesik")
    assert r.status_code == 200
    assert r.json()["price"] == "73804.1900" and r.json()["type"] == "bilesik"


def test_gold_evds_yok_502(monkeypatch):
    monkeypatch.setattr(prices_mod, "fetch_gold_price", lambda t, target=None: None)
    assert client.get("/api/prices/gold/bilesik").status_code == 502


def test_gecersiz_tarih_422(monkeypatch):
    monkeypatch.setattr(prices_mod, "fetch_currency_rate", lambda code, target=None: {"buy": Decimal("1"), "sell": None, "date": "x", "source": "x"})
    r = client.get("/api/prices/currency/USD?date=14/07/2026")
    assert r.status_code == 422


def test_date_gecerli_gecer(monkeypatch):
    seen = {}
    def _cap(code, target=None):
        seen["target"] = target
        return {"buy": Decimal("1"), "sell": Decimal("2"), "date": "d", "source": "s"}
    monkeypatch.setattr(prices_mod, "fetch_currency_rate", _cap)
    r = client.get("/api/prices/currency/USD?date=2026-07-14")
    assert r.status_code == 200 and str(seen["target"]) == "2026-07-14"
