"""
BUG #316 KAPISI — BİNLİK AYIRACI YALNIZ NOKTA DEĞİLDİR.

ÖLÇÜLEN DEFEKT (1 Eylül 2026, ÜRETİM kaydından):
    `reasoning_traces` içinde grounding ölçülen 14 koç cevabının **6'sı (%43)** ihlalli
    görünüyordu. İşaretlenen "uydurma" tutarlar şunlardı: `573.52`, `625.85`, `109.9`,
    `747.22`, `857.12`. Bunlar uydurma DEĞİLDİ — gerçek tutarların KUYRUKLARIYDI:
    4.**573,52** (nakit kasa), 79.**625,85** (kredi borcu), 4.**109,90** ve 2.**747,22**
    (taksitler).

    Sebep: koç tutarları **boşluklu binlik ayıraçla** yazıyor — `4 573,52 TL`,
    `79 625,85 TL`, `15 000 TL`. Türkçede geçerli bir yazımdır ve LLM'lerin doğal
    çıktısıdır. Desen ise binlik ayıracı olarak yalnız NOKTAYI tanıyordu, dolayısıyla
    `4 573,52` metninden sadece `573,52` yakalanıyor, cockpit'te bulunamıyor ve **DOĞRU
    CEVAP "silent hallucination" damgası yiyordu.**

NEDEN BU KAPI ÖNEMLİ (yalnız bir regex hatası değil):
    Zarar sessizdi ve çift yönlüydü.
      (a) `app/coach.py`: `if not grounding["ok"]: confidence = min(confidence, 0.4)` —
          koç DOĞRU cevap verdiğinde bile güven düşürülüyordu.
      (b) `app/coach_eval.py`: `grounded` kriteri aynı dedektöre bağlı → **kalite oranı
          olduğundan KÖTÜ görünüyordu.**
    Dahası: bu dedektöre dayanarak bir "zorlama" (blok/işaretleme) eklenseydi, koçun
    DOĞRU cevapları engellenir ya da damgalanırdı — kullanıcıya aktif zarar.
    **DERS: bir zorlama, ancak ölçütü kadar iyidir; ölçüt doğrulanmadan zorlama eklenmez.**

MUTASYONLA KANITLANDI:
    M1: `_BINLIK`'ten boşluk ailesi çıkarıldı        → çift-yazım testi düşer (ASIL DEFEKT)
    M2: `_etiketli_desen`'deki geriye-bakış silindi  → "sayı ortasından eşleşme" testi düşer
    M3: `_AYIRAC_SIL` boşlukları silmez              → dönüşüm testi düşer
"""
from __future__ import annotations

import pathlib

import pytest

from app.grounding import _to_float_tr, check_grounding

#: Gerçek cockpit değerleri (üretimden alınan tutarlar).
_COCKPIT = {"nakit_kasa": 4573.52, "kredi_borcu": 79625.85, "taksit": 4109.90}

_NBSP = chr(0x00A0)   # kirilmaz bosluk — LITERAL yazilmaz (bkz. asagidaki meta-test)
_NNBSP = chr(0x202F)  # dar kirilmaz bosluk
_INCE = chr(0x2009)   # ince bosluk


# ============================================================
# 1. ASIL DEFEKT — aynı doğru cevap, iki yazım, aynı sonuç
# ============================================================

@pytest.mark.parametrize("ayirac", [".", " ", _NBSP, _NNBSP, _INCE])
def test_ayni_dogru_cevap_her_yazimda_dogrulanir(ayirac):
    """
    Bu testin varlık sebebi: DOĞRU bir cevabın halüsinasyon sanılması. Ayıraç bir YAZIM
    tercihidir; doğruluğu değiştirmez. Kapı bunu her ayıraç için sabitler.
    """
    metin = f"Nakit kasan 4{ayirac}573,52 TL, kredi borcun 79{ayirac}625,85 TL."
    r = check_grounding(metin, _COCKPIT, user_message="durumum ne?")
    assert r["ok"], f"'{ayirac!r}' ayıracıyla doğru cevap ihlalli sayıldı: {r['unverified']}"
    assert not r["unverified"]


def test_uretimde_gorulen_tam_ornek():
    """Üretim kaydından alınan gerçek cümle biçimi (traces'teki ihlalin kaynağı)."""
    metin = (
        "- **Nakit kasada:** 4 573,52 TL\n"
        "- **Kredi borcu:** 79 625,85 TL (iki ayrı kredi)\n"
        "- **Taksit:** 4 109,90 TL"
    )
    r = check_grounding(metin, _COCKPIT, user_message="durum?")
    assert r["ok"], f"üretim örneği hâlâ ihlalli: {r['unverified']}"


# ============================================================
# 2. GERÇEK HALÜSİNASYON HÂLÂ YAKALANIYOR (kapı gevşemedi)
# ============================================================

@pytest.mark.parametrize("ayirac", [".", " ", _NBSP])
def test_gercek_halusinasyon_her_yazimda_yakalanir(ayirac):
    """
    Ayıracı genişletmek dedektörü KÖRLEŞTİRMEMELİ. Yanlış-pozitifi düzeltirken
    yanlış-negatif üretmek, düzeltmeyi anlamsız kılardı.
    """
    metin = f"Nakit kasan 9{ayirac}999,99 TL."
    r = check_grounding(metin, _COCKPIT, user_message="durum?")
    assert not r["ok"], f"'{ayirac!r}' ayıracıyla uydurma tutar kaçtı"
    assert 9999.99 in r["unverified"]


# ============================================================
# 3. YENİ RİSK — eşleşme bir sayının ORTASINDAN başlamasın
# ============================================================

def test_sayinin_ortasindan_eslesme_olmaz():
    """
    Boşluk ayıracı eklenince yeni bir risk doğdu: "2026 300 TL" metninde desen "026 300"
    ile eşleşip **26300** okuyabilirdi — var olmayan bir tutar uydurup onu halüsinasyon
    diye raporlardı. `_etiketli_desen`'e geriye-bakış eklendi.

    ÖRNEK MUTASYONLA DÜZELTİLDİ: ilk yazımda örnek "2026 YILINDA 300 TL"ydi ve araya kelime
    girdiği için eşleşme zaten sayının ortasından başlayamıyordu — yani test, ADINI TAŞIDIĞI
    riski fiilen sınamıyordu (geriye-bakış silindiğinde yeşil kaldı, defekti kardeş test
    yakaladı). Sayılar bitişik olmalı ki risk gerçekten doğsun.
    """
    r = check_grounding("2026 300 TL ödedin.", {"odenen": 300.0}, user_message="?")
    assert r["ok"], f"sayının ortasından eşleşme oldu: {r['unverified']}"


def test_bitisik_sayi_parcasi_yutulmaz():
    """`(?<![\\d.,])` gerçekten çalışıyor mu — 4 haneli yıl + 3 haneli tutar."""
    r = check_grounding("1999 850 TL", {"x": 850.0}, user_message="?")
    assert r["ok"], f"beklenmeyen ihlal: {r['unverified']}"


# ============================================================
# 4. DÖNÜŞÜM — ayıraç ne olursa olsun aynı sayı
# ============================================================

@pytest.mark.parametrize("metin,beklenen", [
    ("4.573,52", 4573.52),
    ("4 573,52", 4573.52),
    ("4" + _NBSP + "573,52", 4573.52),
    ("15 000", 15000.0),
    ("1.234.567,89", 1234567.89),
    ("268,75", 268.75),
])
def test_tr_sayi_donusumu(metin, beklenen):
    assert _to_float_tr(metin) == pytest.approx(beklenen)


# ============================================================
# 5. KAYNAKTA GÖRÜNMEZ KARAKTER OLMAMALI (BUG #312 sınıfı)
# ============================================================

def test_kaynakta_literal_gorunmez_karakter_yok():
    """
    Ayıraç kümesi kaçış dizisiyle (`\\u00A0`) yazılmalı, LİTERAL karakterle değil.
    Kırılmaz/dar/ince boşluklar kaynakta gözle ayırt edilemez; kopyala-yapıştırda ya da
    düzenleyici temizliğinde sessizce kaybolur ve desen körleşir — üstelik hiçbir test
    kırılmadan. BUG #312 aynı sınıftı (docstring'deki `\\v` kaçışı).
    Bu düzeltme sırasında GERÇEKTEN oldu: ilk yazımda literal karakterler kaynağa girdi.
    """
    kaynak = (pathlib.Path(__file__).resolve().parent.parent / "app" / "grounding.py")
    metin = kaynak.read_text(encoding="utf-8")
    bulunan = {
        hex(ord(c)): sum(1 for ch in metin if ch == c)
        for c in (_NBSP, _NNBSP, _INCE)
        if c in metin
    }
    assert not bulunan, f"kaynakta literal görünmez karakter var: {bulunan}"
