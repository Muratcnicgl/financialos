"""
KURAL SIFIR ön-filtresi (BUG #095) — deterministik, LLM gerektirmez.

Kurucu #1 mandat "varsayım yasak": propose_action SADECE gerçekleşmiş eylemde sunulmalı.
Gelecek/niyet ifadesinde ("yarın kapatacağım") ve analiz isteğinde propose_action BASKILANIR.
Baskılamak güvenli yön: yanlış-pozitifte koç netleştirme sorar; yanlış-negatifte eylem UYDURUR.
"""
from __future__ import annotations

import pytest

from app.coach import (
    is_question, is_future_or_intent, has_realized_action, should_offer_propose_tool,
)


# --- Gerçekleşmiş eylem → propose_action SUNULUR ---
REALIZED = [
    "Bugün 500 TL harcadım",
    "Kart borcumu ödedim",
    "3 lot TLY sattım",
    "Maaşım geldi",
    "Efe'ye 1000 TL verdim, kaydet",
]

# --- Gelecek/niyet (gerçekleşmemiş) → propose_action BASKILANIR ---
FUTURE_INTENT = [
    "Yarın kredi kartı borcumu kapatacağım",
    "Gelecek hafta 4 lot TLY satacağım",
    "Önümüzdeki ay krediyi kapatmayı planlıyorum",
    "İleride yatırım yapmayı düşünüyorum",
    "Yarın maaşı çekeceğim",
]

# --- Soru / analiz → propose_action BASKILANIR ---
QUESTIONS = [
    "Kart borcum ne kadar?",
    "Bütçemi değerlendir",
    "Bu ayki harcamalarımı özetle",
    "Borç stratejimi karşılaştır",
    "Durumu göster",
]


@pytest.mark.parametrize("msg", REALIZED)
def test_gerceklesmis_eylem_propose_sunulur(msg):
    assert should_offer_propose_tool(msg) is True, msg


@pytest.mark.parametrize("msg", FUTURE_INTENT)
def test_gelecek_niyet_propose_baskilanir(msg):
    assert should_offer_propose_tool(msg) is False, msg
    assert is_future_or_intent(msg) is True


@pytest.mark.parametrize("msg", QUESTIONS)
def test_soru_analiz_propose_baskilanir(msg):
    assert should_offer_propose_tool(msg) is False, msg


def test_karisik_mesaj_gerceklesen_kismi_korur():
    """'Aldım ama yarın satacağım' — gerçekleşmiş 'aldım' var → propose SUNULUR."""
    msg = "5 lot TLY aldım ama yarın satacağım"
    assert has_realized_action(msg) is True
    assert should_offer_propose_tool(msg) is True


def test_ancak_bacak_gibi_kelimeler_yanlis_pozitif_degil():
    """'ancak' gelecek-eki içermez; yanlış-pozitif üretmemeli."""
    # "ancak" future-ek DEĞİL; bu mesaj gerçekleşmiş eylem içeriyor → propose sunulur
    assert should_offer_propose_tool("Borcumu ödedim ancak azaldı") is True


def test_selamlasma_notr():
    """Selam/bildirim olmayan nötr mesaj: gerçekleşmiş eylem yok, gelecek yok, soru yok.
    Baskılanmaz (mevcut davranış korunur) — LLM zaten KURAL SIFIR prompt'una uyar."""
    # Not: nötr selamda propose sunulur ama LLM prompt gereği çağırmaz.
    assert should_offer_propose_tool("Merhaba") is True
