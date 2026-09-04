"""
BUG #256 (H4) — grounding'in para birimine bağlanması + "etiketsiz tutar" körlüğü.

İKİ DEFEKT VARDI
----------------
1. **Etiket koda gömülüydü.** `grounding._TL_NUM_RE` deseni `…\\s*TL` sabitiyle yazılmıştı.
   Para birimi etiketi değişirse desen hiçbir tutar bulamaz → `checked=0` → fonksiyon
   `{"ok": True}` döner. Yani doğrulama katmanı **vakumsal yeşile** düşer: koç uydurma
   rakam yazsa bile grounding "her şey yolunda" der. (Ders L21 + L28.)
2. **Etiketi olmayan tutarlar hiç denetlenmiyordu.** Koç `"net değerin 31.343"` yazdığında
   (etiket düşmüş) eski kod bunu görmezden geliyordu — halüsinasyon, etiketi yazmayarak
   denetimden kaçabiliyordu. Gerçekten oluyordu: koç bağlamının yatırım K/Z satırı ve kart
   kullanım satırı tutarları **etiketsiz** üretiyordu (bu test dosyasıyla aynı turda düzeltildi).

Bu dosya davranışı ölçer; kapsam tabanı ve yanlış-pozitif sınırı da burada kilitlenir.
"""
from __future__ import annotations

import re

import pytest

from app.grounding import check_grounding, _etiketli_desen, _etiketsiz_desen
from app.money_format import taninan_etiketler, para_etiketi, format_para

COCKPIT = {"nakit_kasa": 4276.14, "kart_borcu": 42100.50, "net_deger": 31343.0}


# ---------------------------------------------------------------- 1. tek kaynak

def test_desen_etiketleri_tek_kaynaktan_gelir():
    """Desen, `money_format.taninan_etiketler()` çıktısındaki HER etiketi tanımalı."""
    for etiket in taninan_etiketler(None):
        metin = f"Bakiye 4.276,14 {etiket}"
        assert _etiketli_desen(None).search(metin), (
            f"{etiket!r} etiketi desende tanınmıyor — tek kaynak ile desen ayrışmış"
        )


def test_grounding_kaynak_kodunda_gomulu_para_etiketi_yok():
    """
    Statik kapı: `grounding.py` içinde ham 'TL' literali kalmamalı — etiket tek kaynaktan
    gelmeli. (Yorum/docstring hariç; onlar davranışı etkilemez.)
    """
    import io
    import tokenize
    from pathlib import Path

    kaynak = Path(__file__).resolve().parent.parent / "app" / "grounding.py"
    metin = kaynak.read_text(encoding="utf-8")

    # Metin taraması YETMEZ: modülün kendi docstring'i bu defekti ANLATIYOR ("…\\s*TL…")
    # ve naif bir arama onu ihlal sanar (yanlış-pozitif). Bu yüzden yorum + string
    # token'ları atılır; yalnız GERÇEK kod incelenir. (Aynı ders: metin ≠ kod, L11 ailesi.)
    kod_parcalari = []
    for tok in tokenize.generate_tokens(io.StringIO(metin).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        kod_parcalari.append(tok.string)
    kod = " ".join(kod_parcalari)

    assert "TL" not in kod, (
        "grounding.py'nin KODUNDA ham para etiketi ('TL') var — etiket "
        "`money_format.taninan_etiketler()` üzerinden gelmeli"
    )
    # Ve gerçekten tek kaynaktan besleniyor mu:
    assert "taninan_etiketler" in kod, "grounding artık tek kaynaktan beslenmeli"


# ---------------------------------------------------- 2. etiketsiz tutar = KIRMIZI

def test_etiketsiz_ve_IZLENEMEYEN_tutar_kirmiziya_duser():
    """
    BUG #256'nın ASIL iddiası: halüsinasyon, para etiketini düşürerek denetimden KAÇAMAZ.

    BUG #321 (2 Eyl 2026) bu testin ÖRNEĞİNİ düzeltti — iddiasını değil. Eski kurgu
    `"Net değerin 31.343 civarında."` idi ve 31.343 `COCKPIT["net_deger"]`in ta kendisiydi;
    yani kapı, DOĞRU bir cümleyi yalnız yazım biçimi yüzünden kırmızı yapıyordu. Canlı
    ölçümde aynı sınıf hata `grounded` kriterini **0/6**'ya düşürmüştü (koç
    `"limit 12.000 (%99,8 dolu)"` yazmıştı ve 12.000 cockpit'te VARDI). Düzeltmeden sonra
    3/6. Örnek artık izlenemeyen bir tutar kullanır — kaçış senaryosunun kendisi.

    KAPSAM DIŞI (bilinçli): BUG #256 "ya da başka birimde" endişesini de yazmıştı. Değer
    eşleşmesi birim farkını göremez; ama ürün tek para birimlidir (`money_format` bilerek
    tek kodludur), yani bu risk bugün yok. Çok para birimi geldiğinde ayrıca ele alınır.
    """
    r = check_grounding("Net değerin 99.999 civarında.", COCKPIT)
    assert r["etiketsiz"] == [99999.0]
    assert r["ok"] is False, "izlenemeyen etiketsiz tutar grounding'i kırmızıya düşürmeli"


def test_etiketsiz_ama_IZLENEBILIR_tutar_yesil_kalir():
    """BUG #321'in diğer yüzü: doğru cevap, yazım biçimi yüzünden cezalandırılamaz."""
    r = check_grounding("Net değerin 31.343 civarında.", COCKPIT)
    assert r["etiketsiz"] == [], "cockpit'te olan sayı 'denetimden kaçış' sayıldı"
    assert r["ok"] is True


def test_etiketsiz_bos_yanit_yesil_kalir():
    """L6: kapı ürünü kıramaz — tutar içermeyen normal cümle yeşil."""
    r = check_grounding("Merhaba, bugün nasıl yardımcı olabilirim?", COCKPIT)
    # BUG #324: `dogrulanan` sözleşmeye EKLENDİ (beraatin gerekçesi). Hiç tutar yoksa boş.
    assert r == {"ok": True, "checked": 0, "unverified": [], "etiketsiz": [],
                 "dogrulanan": []}


def test_etiketli_tutar_etiketsiz_sayilmaz():
    """
    Regresyon (kendi tuzağım): `\\s*(?!ETIKET)` yazımı geri izleyip boşlukta başarılı olur ve
    ETİKETLİ tutarı 'etiketsiz' sayardı. Boşluk lookahead'in içinde olmalı.
    """
    r = check_grounding(f"Nakit {format_para(4276.14)} duruyor.", COCKPIT)
    assert r["etiketsiz"] == []
    assert r["ok"] is True
    assert r["checked"] == 1


# ------------------------------------------------- 3. yanlış-pozitif sınırı (L22)

@pytest.mark.parametrize("metin", [
    "Kart kullanımı %99,8 seviyesinde.",          # yüzde
    "Son ödeme 06.08.2026 tarihinde.",            # tarih
    "Kalan 12.000 gün diye bir şey yok",          # birim: gün
    "2026 yılında başladın.",                     # ayraçsız yıl
    "Toplam 3 taksit kaldı.",                     # küçük düz sayı
    "Fon lotun 2,50 adet.",                       # birim: adet
])
def test_para_olmayan_sayilar_etiketsiz_sayilmaz(metin):
    r = check_grounding(metin, COCKPIT)
    assert r["etiketsiz"] == [], f"yanlış-pozitif: {metin!r} → {r['etiketsiz']}"


def test_esik_altindaki_kucuk_tutar_gurultu_uretmez():
    """min_magnitude altındaki tutarlar (12,50) rapor edilmez — aksi halde kapı gürültü olur."""
    r = check_grounding("Kahve 12,50 tuttu.", COCKPIT)
    assert r["etiketsiz"] == []


# ------------------------------------------------------------- 4. mutasyon kontrolü

def test_kapi_mutasyonu_yakalar():
    """
    Bu testin kendisi işe yarıyor mu: etiketsiz taramasını devre dışı bırakırsak
    'etiketsiz tutar kırmızı' iddiası ÇÖKMELİ. (Fix'i geri alınca test kırmızıya dönmeli.)
    """
    import app.grounding as g
    orijinal = g._etiketsiz_desen
    try:
        g._etiketsiz_desen = lambda kod: re.compile(r"(?!x)x")  # hiçbir şey eşleşmesin
        r = check_grounding("Net değerin 99.999 civarında.", COCKPIT)
        assert r["etiketsiz"] == [] and r["ok"] is True, (
            "mutasyon uygulanamadı — test gerçek davranışı ölçmüyor olabilir"
        )
    finally:
        g._etiketsiz_desen = orijinal
    # mutasyon geri alınınca gerçek davranış geri gelmeli
    assert check_grounding("Net değerin 99.999 civarında.", COCKPIT)["ok"] is False


# ------------------------------------------------------------- 5. sözleşme/kapsam

def test_donus_sozlesmesi_alanlari():
    """
    `etiketsiz` ve (BUG #324) `dogrulanan` sözleşmenin parçası — tüketiciler güvenebilmeli.

    Bu test, alan EKLEMEYİ de yakalar ve bu bilinçli: dönüş sözleşmesi sessizce büyürse
    tüketiciler (eval, chat, trace) hangi alana güvenebileceğini bilemez. BUG #324'te
    kapı değişikliği YAKALADI ve sözleşme burada yazıya döküldü — gevşetilmedi.
    """
    r = check_grounding("Kart borcun 42.100,50 TL.", COCKPIT)
    assert set(r) == {"ok", "checked", "unverified", "etiketsiz", "dogrulanan"}


def test_para_etiketi_varsayilani_tl():
    """Bugünkü ürün kararı: tek para birimi TRY, etiketi 'TL' (ADR-042 / BUG #251)."""
    assert para_etiketi(None) == "TL"
    assert format_para(1234.56) == "1.234,56 TL"
