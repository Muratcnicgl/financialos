"""
BUG #325 KAPISI — ZAYIF BERAAT İŞARETLENİR (ama karar DEĞİŞMEZ).

BUG #324 beraatin gerekçesini görünür kıldı; bu tur o gerekçeyi SAYILABİLİR kılıyor.

ÖLÇÜLEN DAĞILIM (4 Eylül 2026, davranış seti, OpenRouter sabit, 3 koşum, 64 beraat):

    sapma %0,00 (tam eşleşme)            56   %87,5
    sapma %0,00-0,10 (yuvarlama)          3   %4,7    (`2.317` ↔ `2.317,93`, `285` ↔ `285,19`)
    sapma %0,10-1,00                      0   %0,0    <-- BOŞ
    sapma > %1,00                         5   %7,8    (hepsi `12.216` ↔ `12.000`, %1,80)

**Dağılım çift tepeli ve ortası tamamen boş.** Gerçek eşleşmeler ≤ %0,10'da toplanıyor
(tam değer ya da kuruş yuvarlaması), tesadüf ise %1,80'de. Aradaki 18 katlık boşluk,
bir eşiğin ölçümle gerekçelenebileceği en açık durum: **%0,5** ikisinin de uzağında.

ZAYIF BERAATIN ANLAMI (ölçülen örnek): `12.216` = 11.976 + bekleyen 240 TL — koçun
MEŞRU türev sayısı. Kokpit'te yok; `credit_limit` = 12.000'e %1,80 uzaklıkta olduğu için
"izlenebilir" sayıldı. Yani doğru bir sayı, YANLIŞ bir gerekçeyle aklandı. Aynı mekanizma
3 Eylül'de koçun YANLIŞ hesabını (3.536 ↔ 3.600, %1,78) aklamıştı.

**KARAR DEĞİŞMİYOR — VE BU ŞART:**
  · `ok` semantiği aynı: zayıf beraat bir İHLAL DEĞİL, cevap kırmızıya DÜŞMEZ.
  · Tolerans daraltılmıyor: `48.510,41`'i `48.510` yazan doğru cevap düşerdi (BUG #316).
  · Eklenen tek şey bir BAYRAK. Bir sonraki tur canlı veride bunu SAYABİLİR; sayı
    olmadan "kaç beraatimiz şüpheli" sorusu cevaplanamaz.

**ÖRNEKLEM DÜRÜSTLÜĞÜ (yazılı kalsın):** 5 zayıf beraatın 5'i de AYNI tutarın
tekrarıdır — yani bağımsız gözlem sayısı 5 değil, esasen 1. Eşik bu yüzden bir KARAR
kapısı değil, bir SAYAÇ olarak konuldu. Kapıya dönüşmesi için canlı veride daha geniş
bir dağılım gerekir (§10 açık madde).
"""
from __future__ import annotations

from app.grounding import ZAYIF_BERAAT_ESIGI, check_grounding

COCKPIT = {
    "nakit_kasa": 4276.0,
    "kart_borcu": 11976.0,
    "kart_limiti": 12000.0,
    "faiz": 2317.93,
}


def _d(sonuc, tutar):
    for x in sonuc["dogrulanan"]:
        if abs(x["tutar"] - tutar) < 0.01:
            return x
    return None


def test_esik_olculen_bosluga_dusuyor():
    """Eşik, gözlenen iki yığının ARASINDA olmalı — keyfi bir sayı değil."""
    assert 0.10 < ZAYIF_BERAAT_ESIGI < 1.80


def test_TAM_eslesme_zayif_DEGIL():
    assert _d(check_grounding("Kart borcun 11.976 TL.", COCKPIT), 11976.0)["zayif"] is False


def test_KURUS_yuvarlamasi_zayif_DEGIL():
    """Ölçülen meşru yuvarlama: 2.317,93 -> "2.317" (%0,04). Bunu şüpheli saymak yanlış olurdu."""
    d = _d(check_grounding("Toplam faiz 2.317 TL.", COCKPIT), 2317.0)
    assert d["sapma_yuzde"] < ZAYIF_BERAAT_ESIGI and d["zayif"] is False, d


def test_OLCULEN_TESADUF_zayif_isaretlenir():
    """`12.216` (11.976 + bekleyen 240) limite %1,80 uzaklıkta aklanıyordu."""
    d = _d(check_grounding("Kart borcun 12.216 TL olacak.", COCKPIT), 12216.0)
    assert d["dayanak"] == 12000.0 and d["zayif"] is True, d


def test_ZAYIF_BERAAT_CEVABI_KIRMIZIYA_DUSURMEZ():
    """
    En önemli değişmez: bayrak bir İHLAL DEĞİLDİR.

    Kırmızıya düşürmek, koçun meşru türev sayılarını cezalandırmak olurdu — K3'ün
    tüm turu bunun yanlış olduğunu ölçtü (13 düşüşün 13'ü türev/beyan, uydurma 0).
    """
    sonuc = check_grounding("Kart borcun 12.216 TL olacak.", COCKPIT)
    assert sonuc["ok"] is True
    assert sonuc["unverified"] == [] and sonuc["etiketsiz"] == []


def test_zayif_sayisi_toplu_okunabilir():
    """Bir sonraki tur 'kaç beraatimiz şüpheli' diye SAYACAK — tek tek okumayacak."""
    sonuc = check_grounding("Kart borcun 12.216 TL, faiz 2.317 TL, nakit 4.276 TL.", COCKPIT)
    zayiflar = [d for d in sonuc["dogrulanan"] if d["zayif"]]
    assert len(zayiflar) == 1 and zayiflar[0]["tutar"] == 12216.0, sonuc["dogrulanan"]
