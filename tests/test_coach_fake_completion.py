"""
P0-19 / BUG #085: Koc parantezsiz duz gecmis-zaman sahte tamamlama testi.

Kok vizyon "varsayim yasak / kusursuzluk": koc propose_action cagirmadan
"Kaydettim." derse -> hicbir DB yazimi yok ama kullaniciya "islendi" izlenimi
gider (finansal guven kirilir). _postprocess_report bu iddiayi (proposed_actions
bossa) atmali ve netlestirme sorusu eklemeli.

Iki kritik korpus:
- MUST_CATCH: koc'un KENDI sahte tamamlama iddialari -> temizlenmeli.
- MUST_PRESERVE: mesru cevaplar (kullanicinin gecmisi, sorular, analiz) -> DOKUNULMAMALI.
"""
from __future__ import annotations

import pytest

from app.coach import _postprocess_report, _CLARIFY_MSG


# --- Koc'un sahte tamamlama iddiasi (1. TEKİL ŞAHIS, tek-satır): temizlenmeli ---
MUST_CATCH = [
    "Harcamanı kaydettim.",
    "500 TL gideri ekledim.",
    "Tamamdır, işledim.",
    "Kart borcunu güncelledim.",
    "Nakit hesabına geçirdim.",
    "Olur, 250 TL market harcamasını kaydettim, başka bir şey var mı?",
]

# --- Mesru cevaplar: DOKUNULMAMALI (yanlis-pozitif korumasi) ---
# BUG #085 iter2: edilgen 3. şahıs ("işlendi/kaydedildi/geçirildi") ve ÇOK-SATIRLI raporlar
# artık korunuyor — bunlar analiz raporlarında kullanıcının geçmişini betimleyen meşru dil.
MUST_PRESERVE = [
    "Geçen ay toplam 12.000 TL harcama kaydetmişsin.",          # kullanicinin gecmisi
    "Bu ay kaydettiğin işlemler toplam 8.500 TL.",              # katilimci (participle)
    "Hangi hesaptan harcadın? Kartla mı nakitten mi?",          # netlestirme sorusu
    "Kart borcun 42.100 TL, günlük limitin 62 TL.",             # analiz
    "Merhaba! Bugün nasıl yardımcı olabilirim?",                # selamlasma
    "Bu harcamayı kaydetmek ister misin? Onaylarsan eklerim.",  # gelecek/niyet, iddia degil
    "Maaşın 1'inde hesaba geçirildi, 3 fatura da işlendi.",     # EDİLGEN analiz — geçmiş betim
    "İşlem kaydedildi mi diye merak ediyorsan, evet geçen ay.", # edilgen, koç iddiası değil
]

# --- Çok-satırlı yapısal rapor: 1. şahıs iddia içerse bile ASLA bozulmamalı ---
MULTILINE_REPORT = (
    "## 2. FİNANSAL KOKPİT\n"
    "- Kart borcun 42.100 TL\n"
    "- Maaşın hesaba geçirildi, 3 fatura işlendi\n"
    "## 3. STRATEJİ\n"
    "- Bugün nöbet günü, harcama yapma"
)


@pytest.mark.parametrize("text", MUST_CATCH)
def test_sahte_tamamlama_temizlenir(text):
    out = _postprocess_report(text, cockpit={}, user_message="bir şey harcadım", proposed_actions=[])
    # Iddia cumlesi gitmeli
    assert "kaydettim" not in out.lower()
    assert "kaydedildi" not in out.lower()
    assert "ekledim" not in out.lower()
    assert "işledim" not in out.lower()
    assert "güncelledim" not in out.lower()
    # Netlestirme sorusu eklenmeli
    assert _CLARIFY_MSG in out


@pytest.mark.parametrize("text", MUST_PRESERVE)
def test_mesru_cevap_korunur(text):
    out = _postprocess_report(text, cockpit={}, user_message="analiz", proposed_actions=[])
    # Mesru metin oldugu gibi kalmali, netlestirme EKLENMEMELI
    assert out.strip() == text.strip(), f"Yanlis-pozitif: mesru cevap bozuldu -> {out!r}"
    assert _CLARIFY_MSG not in out


def test_proposed_action_varsa_dokunulmaz():
    """Gercek bir aksiyon onerildiyse 'kaydettim' meshru (pending kayit var) -> temizlenmez."""
    text = "250 TL market harcamasını kaydettim, onayına sunuyorum."
    out = _postprocess_report(text, cockpit={}, user_message="market 250",
                              proposed_actions=[{"id": 1, "summary": "market"}])
    assert out.strip() == text.strip()
    assert _CLARIFY_MSG not in out


def test_karma_metin_sadece_iddia_cumlesi_atilir():
    """Tek-satır çoklu cümle: yalniz iddia cumlesi atilir, gerisi korunur."""
    text = "Kart borcun 42.100 TL. Harcamanı kaydettim. Günlük limitin 62 TL."
    out = _postprocess_report(text, cockpit={}, user_message="harcama", proposed_actions=[])
    assert "kaydettim" not in out.lower()
    assert "Kart borcun 42.100 TL" in out
    assert "Günlük limitin 62 TL" in out
    assert _CLARIFY_MSG in out


def test_cok_satirli_rapor_bozulmaz():
    """BUG #085 iter2: çok-satırlı yapısal rapor 1. şahıs iddia içerse bile korunur."""
    out = _postprocess_report(MULTILINE_REPORT, cockpit={}, user_message="analiz et", proposed_actions=[])
    # Rapor yapısı korunmalı — satırlar space'e çökmemeli, başlıklar durmalı
    assert "## 2. FİNANSAL KOKPİT" in out
    assert "## 3. STRATEJİ" in out
    assert "\n" in out  # çok-satır yapısı korundu
    assert _CLARIFY_MSG not in out  # rapora netleştirme sorusu EKLENMEDİ


def test_edilgen_analiz_korunur():
    """BUG #085 iter2: edilgen 3. şahıs ('işlendi/geçirildi') analiz cümlesi korunur."""
    text = "Maaşın 1'inde hesaba geçirildi, 3 fatura da işlendi."
    out = _postprocess_report(text, cockpit={}, user_message="analiz", proposed_actions=[])
    assert out.strip() == text.strip()
    assert _CLARIFY_MSG not in out


# ============================================================
# BUG #094 — kullanıcı kural/checkpoint İSTEDİYSE hedge kelimeye rağmen korunur
# ============================================================

_YC_TEXT = "## YENİ CHECKPOINT\nKart kullanımını %80 ile sınırla, bu kural eklenebilir."


def test_094_kullanici_istediyse_checkpoint_korunur():
    """Kullanıcı 'kural öner' dediyse, 'eklenebilir' hedge kelimesine rağmen öneri kalır."""
    out = _postprocess_report(_YC_TEXT, cockpit={}, user_message="yeni bir kural öner", proposed_actions=[])
    assert "YENİ CHECKPOINT" in out
    assert "sınırla" in out


def test_094_kullanici_istemediyse_checkpoint_silinir():
    """Kontrol: kullanıcı istemediyse istenmeyen checkpoint bölümü eskisi gibi silinir."""
    text = "Kart borcun 42.100 TL.\n" + _YC_TEXT
    out = _postprocess_report(text, cockpit={}, user_message="bütçe durumu nedir", proposed_actions=[])
    assert "YENİ CHECKPOINT" not in out
    assert "Kart borcun 42.100 TL" in out
