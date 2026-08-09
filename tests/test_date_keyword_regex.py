"""
BUG #114 — Türkçe sıralı-tarih (apostrof) yakalama.
Eskiden ['']  düz apostrofları raw string'i erken kapatıp karakter sınıfını boş [] yapıyordu
→ "3'ünde/5'inde" yakalanmıyordu (TARIH_BELIRSIZ tespiti bu tarih formunda çalışmıyordu).

BUG #267: sözleşme sınırı artık DESEN değil `_tarih_ifadesi_var_mi` — desen katlanmış
(diakritiksiz) yazılır ve metin eşleşme öncesi katlanır. Ham desene doğrudan bakan bir test,
"desen ne diyor"u ölçer; korumanın kendisini ölçen giriş noktasıdır. (Kapsam: iki yazım da
`tests/test_niyet_kapisi.py`'de ayrıca parametrize ölçülür.)
"""
from __future__ import annotations

import pytest

from app.action_executor import _tarih_ifadesi_var_mi


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
    assert _tarih_ifadesi_var_mi(text) is True, text


@pytest.mark.parametrize("text", [
    "market alışverişi",
    "kahve içtim",
    "500 TL",
])
def test_tarih_olmayan_yakalanmaz(text):
    assert _tarih_ifadesi_var_mi(text) is False, text
