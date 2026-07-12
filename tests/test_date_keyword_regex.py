"""
BUG #114 — _DATE_KEYWORD_RE Türkçe sıralı-tarih (apostrof) yakalama.
Eskiden ['']  düz apostrofları raw string'i erken kapatıp karakter sınıfını boş [] yapıyordu
→ "3'ünde/5'inde" yakalanmıyordu (TARIH_BELIRSIZ tespiti bu tarih formunda çalışmıyordu).
"""
from __future__ import annotations

import pytest

from app.action_executor import _DATE_KEYWORD_RE


@pytest.mark.parametrize("text", [
    "3'ünde harcadım",
    "ayın 5'inde",
    "12'sinde ödedim",
    "tarihinde",
    "tarihli fatura",
    "12 gün önce",
    "2026-05-01",
    "geçen hafta",
    "şubatta",
])
def test_tarih_ifadeleri_yakalanir(text):
    assert _DATE_KEYWORD_RE.search(text) is not None, text


@pytest.mark.parametrize("text", [
    "market alışverişi",
    "kahve içtim",
    "500 TL",
])
def test_tarih_olmayan_yakalanmaz(text):
    assert _DATE_KEYWORD_RE.search(text) is None, text
