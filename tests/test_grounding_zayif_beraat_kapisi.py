"""
ZAYIF BERAAT ARTIK SESSİZ DEĞİL — BUG #325'in yarım kalan yarısı.

NEDEN VAR (ölçüldü, 10 Eyl 2026, gerçek kullanıcı sohbeti): koç `13.518,48 TL` yazdı.
Böyle bir sayı hiçbir yerde YOKTU — 5 hafta önceki 2.310 TL'lik bir gideri bugünün
nakdinden İKİNCİ kez düşmüştü. Grounding onu beraat ettirdi çünkü tamamen alakasız bir
yaprağa (`nakit_takvimi.toplam_cikis` = 13.434,02) **%0,63** uzaklıktaydı. Kayıtta
`zayif: True` yazıyordu — yani dedektör şüphesini BİLİYORDU — ama:
    `ok` True kaldı · güven 0,9'da durdu · kullanıcı sonraki ÜÇ turda yanlış hesap gördü.

BUG #325 bu bayrağı bilinçli olarak "karar değil SAYAÇ" diye koymuştu ("bir sonraki tur
canlı veride sayılabilsin"). Ama tarama gösterdi: `zayif` kod tabanında **bir tek yerde
yazılıyor, hiçbir yerde okunmuyordu** — loglanmıyor, ize yazılmıyor, hiçbir betik
saymıyordu. Sayaç kuruluydu, kadranı yoktu; beklenen kanıt hiçbir zaman birikemezdi.

BU TUR NE YAPMIYOR: `ok` semantiğini değiştirmiyor, toleransı daraltmıyor, cevabı
kırmızıya düşürmüyor. #325'in ölçülmüş gerekçesi hâlâ geçerli (kapıya dönüşmesi daha geniş
bir dağılım ister) ve saygı duyuluyor.

KİLİTLENEN DEĞİŞMEZLER:
  1. Zayıf beraat sonuçta ÖZETLENİR (`zayif` sayısı + `zayif_tutarlar`) — okunabilir olsun.
  2. `ok` semantiği DEĞİŞMEZ: zayıf beraat tek başına cevabı kırmızı yapmaz.
  3. Tam eşleşme zayıf SAYILMAZ (kapı gürültü üretmesin).
  4. Koç zayıf beraatte güveni kısar — 0,9 ile "doğrulanmadı" aynı şey değildir.
  5. Sayaç koç izine YAZILIR: canlı veride sayılamayan bir sayaç, olmayan sayaçtır.
"""
from __future__ import annotations

import io
import os
import re

from app.grounding import ZAYIF_BERAAT_ESIGI, check_grounding

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_zayif_beraat_sonucta_OZETLENIR():
    """13.518,48 uydurma; 13.434,02'ye %0,63 — beraat ediyor ama zayıf olduğu söylenmeli."""
    cockpit = {"toplam_cikis": 13434.02}
    r = check_grounding("Elinde 13.518,48 TL kalır.", cockpit)
    assert r["zayif"] == 1, f"zayıf beraat özetlenmedi: {r}"
    assert r["zayif_tutarlar"] == [13518.48]


def test_ok_semantigi_DEGISMEDI():
    """#325'in ölçülmüş kararı: zayıf beraat tek başına cevabı kırmızı YAPMAZ."""
    r = check_grounding("Elinde 13.518,48 TL kalır.", {"toplam_cikis": 13434.02})
    assert r["ok"] is True, "zayıf beraat `ok`u düşürmemeli (BUG #316 + #325 gerekçesi)"
    assert r["unverified"] == []


def test_tam_eslesme_zayif_SAYILMAZ():
    """Kapı gürültü üretirse kimse ciddiye almaz (ders L22)."""
    r = check_grounding("Kart borcun 10.020,75 TL.", {"kart_borcu": 10020.75})
    assert r["ok"] is True
    assert r["zayif"] == 0 and r["zayif_tutarlar"] == []


def test_esik_altindaki_yuvarlama_zayif_SAYILMAZ():
    """%0,10'luk yuvarlama gerçek eşleşmedir (#325 dağılımı: gerçekler <=%0,10'da)."""
    r = check_grounding("Tutar 2.317,00 TL.", {"x": 2317.93})
    sapma = abs(2317.00 - 2317.93) / 2317.93 * 100
    assert sapma < ZAYIF_BERAAT_ESIGI
    assert r["zayif"] == 0


def test_koc_zayif_beraatte_GUVENI_KISAR():
    """Kaynak kapısı: 0,9 güvenle doğrulanmamış sayı sunmak, defektin kendisiydi."""
    src = io.open(os.path.join(KOK, "app", "coach.py"), encoding="utf-8").read()
    assert "ZAYIF_BERAAT_GUVEN_TAVANI" in src, "zayıf beraat güven tavanı tanımlı değil"
    assert re.search(r'elif grounding\.get\("zayif"\)', src), \
        "koç zayıf beraat dalını hiç ele almıyor — bayrak yine okunmuyor demektir"
    assert re.search(r"confidence\s*=\s*min\(confidence,\s*ZAYIF_BERAAT_GUVEN_TAVANI\)", src), \
        "güven kısılmıyor"


def test_sayac_KOC_IZINE_yazilir():
    """#325'in vaadi buydu ve tam burası eksikti: sayılamayan sayaç, olmayan sayaçtır."""
    src = io.open(os.path.join(KOK, "app", "coach.py"), encoding="utf-8").read()
    assert "grounding_zayif=" in src, \
        "zayıf beraat sayacı iz kaydına yazılmıyor — canlı veride sayılamaz"


def test_bayrak_artik_OKUNUYOR():
    """#325'in kör noktası: `zayif` bir tek yerde yazılıp hiçbir yerde okunmuyordu.

    Bu kapı o durumun geri gelmesini engeller: bayrağı üreten modülün DIŞINDA en az bir
    tüketici olmalı.
    """
    tuketici = []
    for kok, _, dosyalar in os.walk(os.path.join(KOK, "app")):
        for d in dosyalar:
            if not d.endswith(".py") or d == "grounding.py":
                continue
            yol = os.path.join(kok, d)
            metin = io.open(yol, encoding="utf-8").read()
            if 'grounding.get("zayif")' in metin or 'grounding["zayif' in metin:
                tuketici.append(os.path.relpath(yol, KOK))
    assert tuketici, "zayıf beraat bayrağını `app/` içinde okuyan kimse yok (sayaç yine sağır)"
