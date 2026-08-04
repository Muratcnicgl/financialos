"""
FEAT-032 — Koç için canlı döviz (FX) enjeksiyonu.

get_live_fx: open.er-api payload'ını USD/TRY + EUR/TRY'ye çevirir; hata/ağ → None (uydurma yok).
_maybe_market_block: kullanıcı döviz sorduysa context bloğu + grounding sayıları üretir.
Tümü MOCK (canlı ağ yok → deterministik, flaky değil).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.price_providers import fx_live
from app.coach import _maybe_market_block


class _FakeResp:
    def __init__(self, payload, raise_exc=None):
        self._payload = payload
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clear_cache():
    fx_live._CACHE.clear()
    yield
    fx_live._CACHE.clear()


def _patch_requests(monkeypatch, payload=None, exc=None):
    def fake_get(url, timeout=None):
        if exc:
            raise exc
        return _FakeResp(payload)
    monkeypatch.setattr(fx_live.requests, "get", fake_get)


# ---- get_live_fx --------------------------------------------------------

def test_fx_basarili_parse(monkeypatch):
    _patch_requests(monkeypatch, payload={
        "result": "success",
        "rates": {"TRY": 47.549099, "EUR": 0.868722},
        "time_last_update_utc": "Tue, 04 Aug 2026 00:02:31 +0000",
    })
    fx = fx_live.get_live_fx()
    assert fx is not None
    assert fx["usd_try"] == Decimal("47.5491")
    # EUR/TRY = 47.549099 / 0.868722 ≈ 54.7345
    assert fx["eur_try"] == Decimal("54.7345")
    assert fx["kaynak"] == "open.er-api.com"


def test_fx_result_basarisiz_none(monkeypatch):
    _patch_requests(monkeypatch, payload={"result": "error"})
    assert fx_live.get_live_fx() is None


def test_fx_eksik_oran_none(monkeypatch):
    _patch_requests(monkeypatch, payload={"result": "success", "rates": {"TRY": 47.5}})
    assert fx_live.get_live_fx() is None  # EUR yok


def test_fx_ag_hatasi_none(monkeypatch):
    _patch_requests(monkeypatch, exc=RuntimeError("network down"))
    assert fx_live.get_live_fx() is None  # graceful degradation


def test_fx_cache_ikinci_cagri_ag_kullanmaz(monkeypatch):
    calls = {"n": 0}
    def fake_get(url, timeout=None):
        calls["n"] += 1
        return _FakeResp({"result": "success", "rates": {"TRY": 47.5, "EUR": 0.86},
                          "time_last_update_utc": "x"})
    monkeypatch.setattr(fx_live.requests, "get", fake_get)
    fx_live.get_live_fx()
    fx_live.get_live_fx()
    assert calls["n"] == 1  # ikincisi cache'ten


# ---- _maybe_market_block -----------------------------------------------

def test_block_doviz_kelimesi_yoksa_bos():
    blok, nums = _maybe_market_block("kredilerimi nasıl kapatayım")
    assert blok == "" and nums == []


def test_block_doviz_sorusunda_canli_veri(monkeypatch):
    monkeypatch.setattr("app.price_providers.fx_live.get_live_fx", lambda: {
        "usd_try": Decimal("47.55"), "eur_try": Decimal("54.73"),
        "guncelleme": "Tue, 04 Aug 2026", "kaynak": "open.er-api.com",
    })
    blok, nums = _maybe_market_block("dolar kuru bugün kaç")
    assert "CANLI PİYASA" in blok
    assert "USD/TRY" in blok and "EUR/TRY" in blok
    assert 47.55 in nums and 54.73 in nums


def test_block_veri_alinamazsa_uydurma_notu(monkeypatch):
    monkeypatch.setattr("app.price_providers.fx_live.get_live_fx", lambda: None)
    blok, nums = _maybe_market_block("euro ne kadar")
    assert "alınamadı" in blok.lower() or "çekemedim" in blok.lower()
    assert nums == []  # uydurulacak sayı yok
