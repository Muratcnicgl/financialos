"""
BACKLOG ÖZETİNİ ÜRETİR — elle yazılan özet bayatlar (BUG #348, L74).

NEDEN VAR
---------
`docs/kalite-seruveni/sections/DURUM-INDEX.md` bir ÖZETTİR: 521 maddelik `sections/*.md`
kümesinden türetilmiş sayılar taşır. 5 Eylül 2026 denetiminde ölçüldü ki özet, türetildiği
şeyden **48 gün geride** kalmış: indeks *"RULE'da hâlâ açık: 12"* diyordu, `RULE.md` ise
**0 açık** gösteriyordu (aradaki fark M83'te kapanan beş madde). İndekste `M83` kelimesi
hiç geçmiyordu.

**Ders (L74): türetilmiş bir belge elle güncelleniyorsa, türetildiği şeyden BAĞIMSIZ bir
yalan kaynağıdır — ve özet daha çok okunduğu için zararı daha büyüktür.**

Doğru cevap "bir daha güncellemeyi unutma" notu değil; sayıyı ÜRETMEK. Bu betik
`sections/*.md`'yi okur ve indeksteki işaretli bloğu yeniden yazar. `tests/`deki kapı da
bloğun güncel olduğunu doğrular — yani özet bir daha sessizce bayatlayamaz.

KULLANIM
--------
    python scripts/backlog_ozeti.py          # üretilen bloğu ekrana yazar
    python scripts/backlog_ozeti.py --yaz    # DURUM-INDEX.md içindeki bloğu günceller

Çıkış 2 = KAPI BOZUK (tarayıcı taban altında; ölçmediğini "temiz" sanmamak için — L45).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
BOLUMLER = KOK / "docs" / "kalite-seruveni" / "sections"
INDEKS = BOLUMLER / "DURUM-INDEX.md"

#: İndeks bir madde dosyası değil, bu betiğin ÇIKTISIDIR — kendini saymaz.
HARIC = {"DURUM-INDEX.md"}

#: Tanınan durum işaretleri ve anlamları. İşaretsiz durum yasaktır
#: (`tests/test_backlog_tutarliligi_kapisi.py` bunu zorlar).
ISARET_ANLAMI = {
    "✅": "kapandı",
    "🔲": "açık",
    "🟡": "kısmen",
    "⏸": "kapsam dışı",
    "⚪": "defekt değil",
    "⛔": "yapılmayacak",
}

#: Tarayıcı bozulursa kapı SESSİZCE geçmesin. Bugün 521 madde var.
KAPSAM_TABANI = 400

BASLA = "<!-- OTOMATIK-BACKLOG-OZETI:BASLA — elle düzenleme; `python scripts/backlog_ozeti.py --yaz` -->"
BITTI = "<!-- OTOMATIK-BACKLOG-OZETI:BITTI -->"

_MADDE = re.compile(r"^### \[([A-Z0-9]+-\d+)\]([^\n]*)\n(.*?)(?=^### |\Z)", re.M | re.S)
_DURUM = re.compile(r"^- \*\*Durum:\*\* *(.)", re.M)


def maddeler(kaynaklar: dict[str, str] | None = None) -> list[tuple[str, str, str, str]]:
    """(dosya, kod, başlık, durum-işareti). `kaynaklar` verilirse diskten okumaz (test için)."""
    if kaynaklar is None:
        kaynaklar = {f.name: f.read_text(encoding="utf-8")
                     for f in sorted(BOLUMLER.glob("*.md")) if f.name not in HARIC}
    out = []
    for ad, metin in kaynaklar.items():
        for m in _MADDE.finditer(metin):
            d = _DURUM.search(m.group(3))
            out.append((ad, m.group(1), m.group(2), d.group(1) if d else ""))
    return out


def ozet(kayitlar) -> dict[str, dict[str, int]]:
    """Boyut (dosya adı) → işaret → adet."""
    tablo: dict[str, dict[str, int]] = {}
    for ad, _kod, _baslik, isaret in kayitlar:
        boyut = ad[:-3] if ad.endswith(".md") else ad
        tablo.setdefault(boyut, {}).setdefault(isaret, 0)
        tablo[boyut][isaret] += 1
    return tablo


def metin(kayitlar) -> str:
    """İndekse gömülecek markdown bloğu — sayılar BURADAN gelir, elden değil."""
    tablo = ozet(kayitlar)
    sirali = sorted(ISARET_ANLAMI)
    basliklar = " | ".join(f"{i} {ISARET_ANLAMI[i]}" for i in sirali)
    satirlar = [
        BASLA,
        "",
        f"**Üretildi:** `scripts/backlog_ozeti.py` · **Toplam madde:** {len(kayitlar)}",
        "",
        f"| Boyut | {basliklar} | toplam |",
        "|---" * (len(sirali) + 2) + "|",
    ]
    for boyut in sorted(tablo):
        h = tablo[boyut]
        hucreler = " | ".join(str(h.get(i, 0)) for i in sirali)
        satirlar.append(f"| {boyut} | {hucreler} | {sum(h.values())} |")
    toplamlar = {i: sum(h.get(i, 0) for h in tablo.values()) for i in sirali}
    satirlar.append("| **TOPLAM** | "
                    + " | ".join(f"**{toplamlar[i]}**" for i in sirali)
                    + f" | **{len(kayitlar)}** |")
    satirlar += ["", BITTI]
    return "\n".join(satirlar)


def blogu_degistir(belge: str, yeni_blok: str) -> str:
    i, j = belge.find(BASLA), belge.find(BITTI)
    if i < 0 or j < 0:
        raise SystemExit(
            "DURUM-INDEX.md içinde otomatik blok işaretleri yok. Şu ikisi eklenmelidir:\n"
            f"  {BASLA}\n  {BITTI}"
        )
    return belge[:i] + yeni_blok + belge[j + len(BITTI):]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backlog durum özetini sections/*.md'den üretir.")
    ap.add_argument("--yaz", action="store_true", help="DURUM-INDEX.md içindeki bloğu güncelle.")
    secenek = ap.parse_args(argv)

    kayitlar = maddeler()
    if len(kayitlar) < KAPSAM_TABANI:
        print(f"KAPI BOZUK: yalnız {len(kayitlar)} madde tarandı (taban {KAPSAM_TABANI}). "
              "Bu 'backlog boş' DEMEK DEĞİLDİR — tarayıcı ya da dosya düzeni bozuk.",
              file=sys.stderr)
        return 2

    blok = metin(kayitlar)
    if not secenek.yaz:
        print(blok)
        return 0

    INDEKS.write_text(blogu_degistir(INDEKS.read_text(encoding="utf-8"), blok), encoding="utf-8")
    print(f"DURUM-INDEX.md güncellendi ({len(kayitlar)} madde).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
