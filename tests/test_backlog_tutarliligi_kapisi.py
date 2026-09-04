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

MUTASYON 3/3 — celiskili madde sok -> yalniz celiski testi kirmizi · isaretsiz Durum sok ->
yalniz isaret testi kirmizi · tarayici korlestir -> yalniz kapsam tabani kirmizi
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
BOLUMLER = KOK / "docs" / "kalite-seruveni" / "sections"

#: İndeks bir madde dosyası değil; türetilmiş özettir (kendi bayatlığı ayrı bir konu — L74).
HARIC = {"DURUM-INDEX.md"}

#: Tanınan durum işaretleri. `⛔` = "denendi/ölçüldü, bilinçli olarak YAPILMAYACAK"
#: (MOB-004/005: BUG #288'de canlıda çöktüğü için geri alınan offline önbellek).
#: Yeni bir işaret eklenecekse ANLAMI da buraya yazılır — işaretsiz durum yasaktır.
ISARETLER = "✅🔲🟡⏸⚪⛔"

#: Bugün 521 madde var. Taban, tarayıcı bozulduğunda kapının SESSİZCE geçmesini engeller.
KAPSAM_TABANI = 400

_MADDE = re.compile(r"^### \[([A-Z0-9]+-\d+)\]([^\n]*)\n(.*?)(?=^### |\Z)", re.M | re.S)
_DURUM = re.compile(r"^- \*\*Durum:\*\* *(.)", re.M)


def _maddeler(kaynaklar: dict[str, str] | None = None) -> list[tuple[str, str, str, str]]:
    """(dosya, kod, başlık, gövde) dörtlüleri. `kaynaklar` verilirse diskten okumaz."""
    if kaynaklar is None:
        kaynaklar = {f.name: f.read_text(encoding="utf-8")
                     for f in sorted(BOLUMLER.glob("*.md")) if f.name not in HARIC}
    return [(ad, m.group(1), m.group(2), m.group(3))
            for ad, metin in kaynaklar.items() for m in _MADDE.finditer(metin)]


def _isaretsizler(maddeler) -> list[str]:
    return [f"{ad}:{kod}" for ad, kod, _, govde in maddeler
            if not (_DURUM.search(govde) and _DURUM.search(govde).group(1) in ISARETLER)]


def _celiskiler(maddeler) -> list[str]:
    out = []
    for ad, kod, baslik, govde in maddeler:
        d = _DURUM.search(govde)
        if "✅" in baslik and d and d.group(1) != "✅":
            out.append(f"{ad}:{kod} — başlık ✅ diyor, Durum '{d.group(1)}'")
    return out


def test_KAPSAM_TABANI_tarayici_bozuksa_kapi_BOZULUR():
    """Vakumsal yeşil yasağı: hiçbir madde bulamayan bir tarayıcı 'tutarlı' diyemez."""
    maddeler = _maddeler()
    assert len(maddeler) >= KAPSAM_TABANI, (
        f"KAPI BOZUK: yalnız {len(maddeler)} backlog maddesi tarandı (taban {KAPSAM_TABANI}). "
        "Bu 'backlog tutarlı' DEMEK DEĞİLDİR — tarayıcı ya da dosya düzeni değişmiş."
    )


def test_HER_maddenin_DURUM_isareti_var():
    """DATA-020 regresyon kilidi: girintili ya da işaretsiz Durum satırı sayımdan düşer."""
    kotu = _isaretsizler(_maddeler())
    assert not kotu, (
        "Bu maddelerin `- **Durum:**` satırı yok ya da tanınan bir işaretle başlamıyor "
        f"({ISARETLER}). Böyle bir madde HER otomatik sayımdan düşer ve 'durumu bilinmeyen' "
        f"olarak sessizce yaşar:\n  {kotu}"
    )


def test_BASLIK_ve_DURUM_celismez():
    """FEAT-022/024 regresyon kilidi: aynı girdinin iki satırı birbirini yalanlayamaz."""
    kotu = _celiskiler(_maddeler())
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
    m = _maddeler({"sentetik.md": kaynak})
    assert len(m) == 1
    assert len(_celiskiler(m)) == celiski
    assert len(_isaretsizler(m)) == isaretsiz
