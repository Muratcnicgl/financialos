"""
BUG #374 KAPISI — PROMPT, MODELE YASAKLADIĞI SÖZCÜĞÜ ÖĞRETİYORDU.

ÖLÇÜLEN DURUM (11 Eyl 2026)
---------------------------
2 Eylül'den beri ilk geçerli koç ölçümünde tek gerçek kalite defekti çıktı:
`analiz_grounded_format` → üslup ihlali `IC_JARGON`. İlk refleks "model iç jargon
kullanıyor" demekti. Ölçüm başka bir şey söyledi: sistem promptu **"cockpit"
sözcüğünü 18 kez** kullanıyordu — bölüm başlığında (`# COCKPIT — BUGÜNKÜ DURUM`),
kurallarda ("Cockpit verisinde olmayan hiçbir tutarı uydurma") ve yasağın KENDİ
cümlesinde ("Cockpit alan adları … YASAK"). Sonra aynı prompt modele "cockpit deme"
diyordu. Model, verilen sözcüğü yansıtıyordu; kusur modelde değil prompt tasarımındaydı.

Üstüne bir de arayüzle çelişki vardı: sekme etiketi sade görünümde "Özet", detaylı
görünümde "Cockpit". Her iki görünümde de anlaşılır tek sözcük "panel" (arayüzün
`aria-label="Paneller"`i ve koçun kendi düşme mesajı da öyle diyor). Prompt o dile
çevrildi: cockpit → panel (19 yer), "Rules Engine" → "sistem", "ADR-001" düştü.

BU KAPI NE ÖLÇER
----------------
`app.uslup_kurallari.IC_JARGON` desenleri, modele giden SABİT prompt metninde
eşleşmemeli. İki bilinçli istisna:
  · `propose_action` ve `payload` — araç ADI ve araç çağrısının gövdesi; araç
    mekaniği anlatılırken ("payload'a transaction_date EKLEME") geçmek zorunda. Yasak
    kullanıcıya giden CEVAP içindir, araç şeması için değil. Ölçüldü: üç `payload`
    geçişinin üçü de YALNIZ araçlı prompt'ta ve yalnız şablon talimatlarında.
  · Yasağın kendi paragrafı — örnek olarak "90 günlük forecast" diye yazar; yasak,
    yasakladığı şeyi adlandırmak zorundadır.

Bunun dışında her eşleşme, modele öğretilen bir jargon sözcüğüdür ve kapı kırmızı verir.
"""
from __future__ import annotations

import re

from app.coach import V3_GOD_MODE_PROMPT, sistem_promptu
from app.uslup_kurallari import KURALLAR

IZINLI = {"propose_action", "payload"}


def _yasak_paragrafi_cikar(metin: str) -> str:
    """Yasağın kendi paragrafını (İÇ JARGON YASAĞI … boş satıra kadar) metinden düşer."""
    i = metin.find("İÇ JARGON YASAĞI")
    if i < 0:
        return metin
    j = metin.find("\n\n", i)
    return metin[:i] + (metin[j:] if j > 0 else "")


def _eslesmeler(metin: str) -> list[str]:
    kural = next(k for k in KURALLAR if k.kod == "IC_JARGON")
    metin = _yasak_paragrafi_cikar(metin)
    bulunan = []
    for desen in kural.desenler:
        for m in re.finditer(desen, metin, re.IGNORECASE):
            if m.group(0).lower() not in IZINLI:
                bulunan.append(m.group(0))
    return bulunan


def test_ARACLI_prompt_jargon_ogretmez():
    b = _eslesmeler(V3_GOD_MODE_PROMPT)
    assert b == [], f"prompt modele yasakladığı sözcükleri öğretiyor: {sorted(set(b))}"


def test_ARACSIZ_prompt_jargon_ogretmez():
    b = _eslesmeler(sistem_promptu(False))
    assert b == [], f"araçsız prompt modele yasakladığı sözcükleri öğretiyor: {sorted(set(b))}"


def test_baglam_basligi_kullanici_dilinde():
    """Kokpit bağlamının başlığı da prompt'un parçasıdır — `# COCKPIT` yerine `# PANEL`."""
    import inspect

    import app.coach as coach

    kaynak = inspect.getsource(coach)
    assert "# PANEL — BUGÜNKÜ DURUM" in kaynak, "bağlam başlığı kullanıcı diline çevrilmemiş"
    assert "# COCKPIT — BUGÜNKÜ DURUM" not in kaynak, "eski başlık hâlâ modele gidiyor"


def test_kapi_KENDISI_calisiyor():
    """Denetleyiciyi denetle: yasaklı sözcük içeren bir metinde kapı gerçekten kırmızı mı?"""
    assert _eslesmeler("Cockpit'teki rakamlara göre durumun iyi.") != []
    assert _eslesmeler("Paneldeki rakamlara göre durumun iyi.") == []
    assert _eslesmeler("propose_action aracı bu turda kapalı") == [], "araç adı izinli olmalı"
