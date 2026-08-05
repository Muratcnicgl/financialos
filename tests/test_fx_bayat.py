"""
H16 / BUG #211 — sağlayıcı düştüğünde kur bilgisi TAMAMEN kayboluyordu.

Eski davranış: 31 dakika önce başarıyla çekilmiş bir kur elde dururken, sağlayıcıya
erişilemediği an koç "çekemedim, bankana bak" diyordu. Ücretsiz sağlayıcının birkaç
saatlik kesintisi rutindir; o süre boyunca ürün kur konusunda tümüyle sessizleşiyordu.

Diğer uç daha da tehlikeli: bayat değeri sessizce "şu anki kur" diye sunmak — kullanıcı
eski kura göre karar verir. Bu dosya iki ucu da kilitler: değer BAYAT İŞARETİYLE döner,
koç dili değişir, ve tavan yaşı (12 saat) aşan değer HİÇ dönmez.
"""
from __future__ import annotations

import time
from decimal import Decimal

import pytest

from app.price_providers import fx_live


class _Yanit:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


_BASARILI = {"result": "success", "rates": {"TRY": 41.5, "EUR": 0.92},
             "time_last_update_utc": "Tue, 05 Aug 2026 00:00:01 +0000"}


@pytest.fixture(autouse=True)
def temiz_cache():
    fx_live._CACHE.clear()
    yield
    fx_live._CACHE.clear()


def _basarili_cek(monkeypatch):
    monkeypatch.setattr(fx_live.requests, "get", lambda *a, **k: _Yanit(_BASARILI))
    return fx_live.get_live_fx()


def test_taze_cekim_bayat_degil(monkeypatch):
    fx = _basarili_cek(monkeypatch)
    assert fx["bayat"] is False and fx["usd_try"] == Decimal("41.5000")


def test_saglayici_dusunce_son_bilinen_deger_doner(monkeypatch):
    """Kesintide ürün susmamalı — son bilinen kur işaretlenerek sunulur."""
    _basarili_cek(monkeypatch)
    # cache'i TTL dışına it (45 dk önce çekilmiş gibi) ve sağlayıcıyı düşür
    data, ts = fx_live._CACHE["fx"]
    fx_live._CACHE["fx"] = (data, ts - 45 * 60)

    def _patla(*a, **k):
        raise ConnectionError("ağ yok")

    monkeypatch.setattr(fx_live.requests, "get", _patla)
    fx = fx_live.get_live_fx()
    assert fx is not None, "Kesintide son bilinen kur kayboldu (ürün sessizleşti)"
    assert fx["bayat"] is True
    assert 44 <= fx["yas_dakika"] <= 46
    assert fx["usd_try"] == Decimal("41.5000")


def test_bozuk_yanit_da_bayat_degere_duser(monkeypatch):
    _basarili_cek(monkeypatch)
    data, ts = fx_live._CACHE["fx"]
    fx_live._CACHE["fx"] = (data, ts - 60 * 60)
    monkeypatch.setattr(fx_live.requests, "get", lambda *a, **k: _Yanit({"result": "error"}))
    fx = fx_live.get_live_fx()
    assert fx and fx["bayat"] is True


def test_cok_eski_deger_hic_donmez(monkeypatch):
    """12 saati aşan kur yanıltıcıdır — faydası riskini geçmez."""
    _basarili_cek(monkeypatch)
    data, ts = fx_live._CACHE["fx"]
    fx_live._CACHE["fx"] = (data, ts - (fx_live._BAYAT_TAVAN_DK + 5) * 60)
    monkeypatch.setattr(fx_live.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert fx_live.get_live_fx() is None


def test_hic_veri_yokken_none(monkeypatch):
    monkeypatch.setattr(fx_live.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert fx_live.get_live_fx() is None


def test_bayat_kopya_cache_i_kirletmez(monkeypatch):
    """Bayat işaret son BAŞARILI kayda yazılmamalı (yoksa taze çekim de bayat görünür)."""
    _basarili_cek(monkeypatch)
    data, ts = fx_live._CACHE["fx"]
    fx_live._CACHE["fx"] = (data, ts - 45 * 60)
    monkeypatch.setattr(fx_live.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    fx_live.get_live_fx()
    assert fx_live._CACHE["fx"][0].get("bayat") is False


# ── Koç dili: bayat değeri "şu anki kur" diye sunulamaz ──────────────────────

def test_koc_bloku_bayati_acikca_soyler(monkeypatch):
    from app.coach import _maybe_market_block
    monkeypatch.setattr("app.price_providers.fx_live.get_live_fx",
                        lambda: {"usd_try": Decimal("41.5"), "eur_try": Decimal("45.1"),
                                 "guncelleme": "?", "kaynak": "t", "bayat": True,
                                 "yas_dakika": 125})
    blok, sayilar = _maybe_market_block("dolar kuru kaç?")
    assert "BAYAT" in blok and "2 saat 5 dakika" in blok
    assert "ŞU ANKİ GÜNCEL KUR" not in blok, "Bayat değer 'şu anki kur' diye sunuluyor"
    assert sayilar == [41.5, 45.1], "Grounding sayıları kaybolursa koç değeri yazamaz"


def test_koc_bloku_taze_veride_canli_der(monkeypatch):
    from app.coach import _maybe_market_block
    monkeypatch.setattr("app.price_providers.fx_live.get_live_fx",
                        lambda: {"usd_try": Decimal("41.5"), "eur_try": Decimal("45.1"),
                                 "guncelleme": "x", "kaynak": "t", "bayat": False,
                                 "yas_dakika": 0})
    blok, _ = _maybe_market_block("dolar kuru kaç?")
    assert "ŞU ANKİ GÜNCEL KUR" in blok and "BAYAT" not in blok
