"""
parse_gg_command — 'gg' hızlı harcama komut çözümleyici (kullanıcı-yüzü).
Mimari belgesinde tanımlı üç format + ondalık, çok-kelime kategori, eşleşmeme, büyük/küçük harf.
"""
from __future__ import annotations

from app.rules_engine import parse_gg_command as p


def test_varsayilan_kart():
    r = p("gg 50 yemek")
    assert r == {"amount": 50.0, "category": "yemek", "source": "kart", "is_card": True}


def test_nakit_kaynagi():
    r = p("gg nakit 50 ulaşım")
    assert r["source"] == "nakit"
    assert r["is_card"] is False
    assert r["amount"] == 50.0
    assert r["category"] == "ulaşım"


def test_acik_kart_kaynagi():
    r = p("gg kart 120 alışveriş")
    assert r["source"] == "kart" and r["is_card"] is True
    assert r["amount"] == 120.0


def test_ondalik_nokta_ve_virgul():
    assert p("gg 50.5 kahve")["amount"] == 50.5
    assert p("gg 50,5 kahve")["amount"] == 50.5


def test_cok_kelimeli_kategori():
    assert p("gg 100 market alışverişi")["category"] == "market alışverişi"


def test_buyuk_harf_ve_bosluk():
    r = p("  GG 75 KAHVE  ")
    assert r["amount"] == 75.0
    assert r["category"] == "kahve"    # lowercase'e çevrilir


def test_eslesmeyen_none():
    assert p("merhaba") is None
    assert p("gg") is None
    assert p("gg yemek") is None       # miktar yok
    assert p("50 yemek") is None       # gg öneki yok
