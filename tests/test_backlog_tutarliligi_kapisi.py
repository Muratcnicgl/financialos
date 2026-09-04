"""
BACKLOG TUTARLILIK KAPISI (BUG #347 — 5 Eylül 2026).

NEDEN VAR
---------
`sections/*.md` 521 backlog maddesi taşıyor ve her maddenin durumu iki yerde yazılı:
başlık satırındaki inline işaret (`✅ UYGULANDI`) ve greplenebilir `- **Durum:**` satırı.
`sections/DURUM-INDEX.md`'nin metodoloji notu ikisinin BİRLİKTE güncellenmesini şart
koşuyor — *"böylece backlog bir daha sessizce bayatlamaz"*.

5 Eylül denetiminde o kuralın üç yerde tutmadığı ÖLÇÜLDÜ:

1. **FEAT-022 ve FEAT-024** — başlıkta `✅ UYGULANDI`, `- **Durum:**` satırında `🔲`/`🟡`.
   Aynı girdinin iki satırı birbirini yalanlıyordu. Kodla doğrulandı: ikisi de kapalı
   (`rules_engine.calculate_health_score` · `calculate_real_networth`). Yani greplenebilir
   olan yarı YANLIŞ kalmıştı; **otomatik sayımlar bu iki maddeyi 48 gün boyunca "açık"
   saydı.**
2. **DATA-020** — `- **Durum:**` satırı GİRİNTİLİ yazılmış ve hiç durum işareti
   taşımıyordu. Madde ölçüldüğünde düzelmiş çıktı (hard-coded `account_id=2` kalmamış),
   ama biçim yüzünden her sayımdan düşüyordu: **"durumu bilinmeyen" tek maddeydi ve
   kimse fark etmedi** — L45'in backlog karşılığı (bilinmeyen ≠ sıfır).

NE ZORLAR
---------
* Her maddenin sütun 0'da, tanınan bir işaretle başlayan bir `- **Durum:**` satırı olur.
* Başlığı `✅` diyen bir madde, `- **Durum:**` satırında da `✅` demek zorundadır.
  (Tersi serbest: bir madde başlık işareti olmadan da kapanmış olabilir.)
* Tarayıcı boşa düşerse kapı **geçmez, BOZULUR** — 521 maddelik bir dosya kümesinde
  40 madde bile bulamayan bir tarayıcı "her şey tutarlı" diyemez (vakumsal yeşil yasağı).

Bu bir ÜSLUP kapısı değil, bir ÖLÇÜM kapısıdır: greplenebilir alan yanlışsa, ona dayanan
her sayım — durum raporları dahil — yanlış olur.

MUTASYON 4/4 — celiskili madde sok · isaretsiz (girintili) Durum sok · tarayiciyi korlestir ·
uretilmis ozeti ELLE degistir. Dorduncusu BUG #348'in kilidi: ozet, sections/*.md ile
uyusmazsa kirmizi. (Son iki mutasyon guncellik testini de dusurur — veri degisince uretilen
ozet de degisir; bu asiri atesleme degil, gercek bagimlilik.)

AYRICA BU KAPI KENDI KOR NOKTASINI BULDURDU: isaretsiz maddeyi arayan kontrol
`isaret not in ISARETLER` diye yazilmisti; Python'da `"" in "abc"` **True** doner, yani
hic isareti olmayan madde sessizce GECIYORDU. Sentetik ornek mutasyonu bunu yakalatti.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

# AYRIŞTIRICI KOPYALANMAZ — tek kaynak `scripts/backlog_ozeti.py`. Kapı ile üretici aynı
# maddeleri görmezse biri diğerini doğrulamaz; `git ls-files`in beş kopyasıyla aynı ders (L71).
from scripts.backlog_ozeti import (  # noqa: E402
    BASLA, BITTI, INDEKS, ISARET_ANLAMI, KAPSAM_TABANI, maddeler, metin,
)

ISARETLER = "".join(ISARET_ANLAMI)


def _isaretsizler(kayitlar) -> list[str]:
    # `""` her dizgenin alt dizgesidir: `"" in ISARETLER` **True** döner. Boşluk ayrıca
    # kontrol edilmezse işaretsiz madde sessizce geçerdi — kapının kendi kör noktasıydı,
    # sentetik örnek mutasyonu buldurdu.
    return [f"{ad}:{kod}" for ad, kod, _baslik, isaret in kayitlar
            if not isaret or isaret not in ISARETLER]


def _celiskiler(kayitlar) -> list[str]:
    return [f"{ad}:{kod} — başlık ✅ diyor, Durum '{isaret}'"
            for ad, kod, baslik, isaret in kayitlar
            if "✅" in baslik and isaret and isaret != "✅"]


def test_KAPSAM_TABANI_tarayici_bozuksa_kapi_BOZULUR():
    """Vakumsal yeşil yasağı: hiçbir madde bulamayan bir tarayıcı 'tutarlı' diyemez."""
    kayitlar = maddeler()
    assert len(kayitlar) >= KAPSAM_TABANI, (
        f"KAPI BOZUK: yalnız {len(kayitlar)} backlog maddesi tarandı (taban {KAPSAM_TABANI}). "
        "Bu 'backlog tutarlı' DEMEK DEĞİLDİR — tarayıcı ya da dosya düzeni değişmiş."
    )


def test_HER_maddenin_DURUM_isareti_var():
    """DATA-020 regresyon kilidi: girintili ya da işaretsiz Durum satırı sayımdan düşer."""
    kotu = _isaretsizler(maddeler())
    assert not kotu, (
        "Bu maddelerin `- **Durum:**` satırı yok ya da tanınan bir işaretle başlamıyor "
        f"({ISARETLER}). Böyle bir madde HER otomatik sayımdan düşer ve 'durumu bilinmeyen' "
        f"olarak sessizce yaşar:\n  {kotu}"
    )


def test_BASLIK_ve_DURUM_celismez():
    """FEAT-022/024 regresyon kilidi: aynı girdinin iki satırı birbirini yalanlayamaz."""
    kotu = _celiskiler(maddeler())
    assert not kotu, (
        "Başlığı kapandığını söyleyen ama Durum satırı öyle demeyen maddeler var. "
        "Greplenebilir alan Durum satırıdır; yanlış kalırsa raporlar da yanlış olur:\n  "
        + "\n  ".join(kotu)
    )


# ── Meta-testler: KAPI ÇALIŞIYOR MU? (yeşil kapı, çalışan kapı demek değildir) ──

_CELISKILI = "### [XX-001] Bir sey ✅ UYGULANDI\n- **Durum:** 🔲 AÇIK\n\n- **Sorun:** x\n"
_ISARETSIZ = "### [XX-002] Baska sey\n  - **Durum:** duz metin, isaret yok\n\n- **Sorun:** x\n"
_TEMIZ = "### [XX-003] Ucuncu sey ✅ UYGULANDI\n- **Durum:** ✅ KAPANDI\n\n- **Sorun:** x\n"


@pytest.mark.parametrize("kaynak,celiski,isaretsiz", [
    (_CELISKILI, 1, 0),
    (_ISARETSIZ, 0, 1),
    (_TEMIZ, 0, 0),
])
def test_KAPI_sentetik_ornekleri_dogru_ayirir(kaynak, celiski, isaretsiz):
    """Kapı, iki ihlali BİRBİRİNDEN de ayırmalı — tek bir 'bozuk' kovası yetmez."""
    m = maddeler({"sentetik.md": kaynak})
    assert len(m) == 1
    assert len(_celiskiler(m)) == celiski
    assert len(_isaretsizler(m)) == isaretsiz


def test_INDEKS_OZETI_GUNCEL_kalir():
    """BUG #348 / L74 — türetilmiş özet, türetildiği şeyden bağımsız bayatlayamaz.

    `DURUM-INDEX.md` 48 gün boyunca *"RULE'da hâlâ açık: 12"* dedi; `RULE.md` ise 0 açık
    gösteriyordu. Özeti elle güncellemeyi hatırlamak bir mekanizma değildir — bu test,
    indeksteki üretilmiş bloğun BUGÜNKÜ `sections/*.md`'den üretilenle birebir aynı
    olmasını şart koşar.
    """
    belge = INDEKS.read_text(encoding="utf-8")
    i, j = belge.find(BASLA), belge.find(BITTI)
    assert i >= 0 and j > i, (
        "DURUM-INDEX.md içinde otomatik özet bloğu yok. Sayılar elle yazılırsa bayatlar. "
        f"Blok işaretleri geri konmalı: {BASLA} ... {BITTI}"
    )
    mevcut = belge[i:j + len(BITTI)]
    beklenen = metin(maddeler())
    assert mevcut == beklenen, (
        "DURUM-INDEX.md'deki özet, sections/*.md ile uyuşmuyor (yani bayat). "
        "Düzelt: python scripts/backlog_ozeti.py --yaz"
    )
