"""
ARAÇ MEKANİĞİ KOŞULLU GÖNDERİLİR — prompt bütçesinin ilk gerçek indirimi.

ÖLÇÜLEN DEFEKT (10 Eyl 2026, canlı sağlayıcılarla): koçun tek isteği 10.430 token.
Elimizdeki her ücretsiz kademe bunun altında:
    Groq   : "Limit 8000, Requested 10430"  (413, her modelde 7.000-8.000 TPM)
    Gemini : günde 20 istek (quotaValue: '20') -> ~10 koç mesajı
Sonuç: koç, erişilebilir en yetenekli modele (gpt-oss-120b) HİÇ ulaşamıyor; sınıfının en
küçük modeline mahkûm kalıyor. `test_prompt_butcesi_kapisi.py` bu döngüyü 1 Eyl'de teşhis
edip FREN koymuştu (tavan = o günkü boyut) ama küçültmeyi kimse yapmadı — fren büyümeyi
durdurur, boyutu düşürmez. Bu kapı, indirimin kendisini kilitler.

KESMENİN MANTIĞI: `offer_propose=False` olan turda `propose_action` aracı modele HİÇ
verilmiyor (`active_tools` yalnız `save_insight`). O turda aracın MEKANİĞİNİ (tetikleyici
fiiller, sınıflandırma tablosu, payload alanları, özet kuralları) göndermek, modelin
uygulayamayacağı bir talimatı okutmaktır. Uygulanamaz talimat = ölü ağırlık.

KESİLMEYEN (bilerek): sahte niyet / sahte tamamlama / varsayım-halüsinasyon / ADR-001
hesap uydurma / doğru çerçeveyle başlama / sızdırma yasağı. Bunlar araç YOKKEN daha da
kritiktir — "kaydettim" demenin bedeli tam da araç yokken ödenir.
"""
from __future__ import annotations

import io
import os
import re

from app.coach import (
    ARAC_KAPALI_NOTU,
    V3_GOD_MODE_PROMPT,
    _ARAC_MEKANIGI_BLOKLARI,
    sistem_promptu,
)

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 1 Eyl 2026'da GERÇEK tokenizer'la ölçülen oran (bkz. test_prompt_butcesi_kapisi).
KARAKTER_BASINA_TOKEN = 2.84

#: Araç kapalı promptun TAVANI. Bugün ölçülen 14.796 karakter; pay bırakılmadı çünkü
#: sözleşme (aynı dosyanın kardeşi) tavanı yalnız AŞAĞI çekmeyi kabul eder.
TAVAN_KARAKTER_ARAC_KAPALI = 14_796

#: Kesmenin ANLAMLI olduğunun alt sınırı. Bu sayının altına düşerse "kestik" iddiası
#: gürültüye dönüşür ve blok sınırları sessizce kaymış demektir.
ASGARI_KAZANC_KARAKTER = 4_000


def test_arac_ACIKKEN_prompt_birebir_ayni():
    """Araç açıkken hiçbir şey kaybolmaz — indirim koşulludur, kalıcı silme DEĞİL."""
    assert sistem_promptu(True) == V3_GOD_MODE_PROMPT


def test_arac_kapaliyken_OLCULEBILIR_kazanc_var():
    kazanc = len(sistem_promptu(True)) - len(sistem_promptu(False))
    assert kazanc >= ASGARI_KAZANC_KARAKTER, (
        f"kazanç {kazanc} karakter — blok sınırları kaymış olabilir "
        f"(beklenen >= {ASGARI_KAZANC_KARAKTER})"
    )


def test_arac_kapali_prompt_TAVANI_asmaz():
    """Kardeş sözleşme: tavan yalnız AŞAĞI çekilir; küçülünce buraya yazılır."""
    olculen = len(sistem_promptu(False))
    assert olculen <= TAVAN_KARAKTER_ARAC_KAPALI, (
        f"araç-kapalı prompt şişti: {olculen} > {TAVAN_KARAKTER_ARAC_KAPALI}"
    )


def test_uc_blok_da_bulunmus():
    """Sınırlar kayarsa `find` sessizce boş döner ve kesme hiç olmaz — sessiz ölüm."""
    assert len(_ARAC_MEKANIGI_BLOKLARI) == 3, (
        f"araç mekaniği blokları bulunamadı ({len(_ARAC_MEKANIGI_BLOKLARI)}/3) — "
        "prompt metni değişmiş, sınırlar güncellenmeli"
    )
    for blok in _ARAC_MEKANIGI_BLOKLARI:
        assert len(blok) > 500, f"blok şüpheli kısa ({len(blok)} kr) — sınır kaymış olabilir"


def test_KESILMEYEN_yasaklar_arac_kapaliyken_de_DURUYOR():
    """Kesmenin kırmızı çizgisi. Bunlardan biri düşerse indirim güvenlik kaybına döner."""
    kapali = sistem_promptu(False)
    for yasak in (
        "SAHTE NİYET YASAĞI",
        "SAHTE TAMAMLAMA YASAĞI",
        "VARSAYIM VE HALÜSİNASYON",
        "HESAP UYDURMA YASAĞI",       # ADR-001
        "DOĞRU ÇERÇEVEYLE BAŞLA",
        "SIZDIRMA YASAĞI",            # META KURAL
        "# KARAKTER",
        "# KURALLAR",
    ):
        assert yasak in kapali, f"araç kapalıyken kaybolmaması gereken bölüm gitti: {yasak}"


def test_KESILEN_mekanik_arac_kapaliyken_YOK():
    kapali = sistem_promptu(False)
    for mekanik in (
        "# AKSIYON SEÇİM TABLOSU",
        "# PAYLOAD ŞABLONLARI",
        "HESAP TAHMİNİ YASAĞI",
        "TARİH ECHO YASAĞI",
    ):
        assert mekanik not in kapali, f"araç mekaniği hâlâ gönderiliyor: {mekanik}"


def test_baslik_sessizce_silinmez_yerine_NOT_konur():
    """Başlığı silip yasakları başlıksız bırakmak, modele 'kaydedebilirim' izlenimi verir."""
    kapali = sistem_promptu(False)
    assert ARAC_KAPALI_NOTU in kapali
    assert "AKSIYON ARACI BU TURDA KAPALI" in kapali
    assert len(ARAC_KAPALI_NOTU) < 400, "not, yerine geçtiği bloktan büyük olmamalı"


def test_chat_KOSULLU_olarak_kullaniyor():
    """Fonksiyon var ama çağrılmıyorsa kazanç kâğıt üstünde kalır (bkz. `zayif` bayrağı)."""
    src = io.open(os.path.join(KOK, "app", "coach.py"), encoding="utf-8").read()
    assert re.search(r"if not offer_propose:\s*\n\s*system_prompt = system_prompt\.replace\(",
                     src), "sistem_promptu(False) chat() içinde kullanılmıyor"


def test_kazanc_token_olarak_anlamli():
    """Ölçülen oranla (~2,84 kr/token) kazanç, Groq'un 8.000 TPM'i için anlamlı olmalı."""
    kazanc_kr = len(sistem_promptu(True)) - len(sistem_promptu(False))
    kazanc_token = kazanc_kr / KARAKTER_BASINA_TOKEN
    assert kazanc_token > 1_400, f"token kazancı düşük: ~{kazanc_token:.0f}"
