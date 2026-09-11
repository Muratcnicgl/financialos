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

#: BUG #375 — `backlog.md`'deki "Öne çıkan canlı bug'lar" listesi de ELLE yazılmıştı ve
#: 11 Eyl 2026'da ölçüldü: yedi maddenin BEŞİ bölüm dosyalarında ✅ kapalıyken belge hâlâ
#: "canlı" diyordu (RULE-001, DATA-003, SEC-001, RULE-006, FE-002). DURUM-INDEX'in 48 gün
#: geride kalmasıyla aynı hastalık, aynı ilaç: SEÇİM insanındır (hangi maddeler önemli),
#: DURUM ölçümündür (açık mı kapalı mı). Kodlar burada durur, durumları `sections/`ten gelir.
ONCELIKLI_KODLAR = (
    "RULE-001", "RULE-002", "RULE-003", "RULE-004", "RULE-005", "RULE-006", "RULE-040",
    "FE-002", "FE-026", "BE-009", "API-004", "RESIL-016", "SEC-001", "DATA-003",
)
BACKLOG = KOK / "docs" / "kalite-seruveni" / "backlog.md"
ONCELIK_BASLA = "<!-- OTOMATIK-ONCELIK:BASLA — elle düzenleme; `python scripts/backlog_ozeti.py --yaz` -->"
ONCELIK_BITTI = "<!-- OTOMATIK-ONCELIK:BITTI -->"

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


def oncelik_metni(kayitlar) -> str:
    """`backlog.md`'ye gömülecek "öncelikli maddeler" bloğu — DURUM sections'tan gelir.

    Açık olanlar üstte (🔲, 🟡), kapananlar altta ve açıkça "kapandı" diye; listede
    olup sections'ta bulunmayan kod da GİZLENMEZ, "bulunamadı" diye yazılır (L45).
    """
    haritasi = {kod: (baslik.strip(), isaret) for _ad, kod, baslik, isaret in kayitlar}
    acik, kapali, kayip = [], [], []
    for kod in ONCELIKLI_KODLAR:
        if kod not in haritasi:
            kayip.append(kod)
            continue
        baslik, isaret = haritasi[kod]
        hedef = acik if isaret in ("🔲", "🟡") else kapali
        hedef.append(f"- {isaret} **{kod}** — {baslik} ({ISARET_ANLAMI.get(isaret, '?')})")
    satirlar = [
        ONCELIK_BASLA,
        "",
        f"**Üretildi:** `scripts/backlog_ozeti.py` · seçim elle, durum `sections/`ten · "
        f"**{len(acik)} açık / {len(kapali)} kapandı**",
        "",
    ]
    satirlar += acik or ["- (öncelikli listede açık madde kalmadı)"]
    if kapali:
        satirlar += ["", "<details><summary>Kapananlar</summary>", ""] + kapali + ["", "</details>"]
    if kayip:
        satirlar += ["", "⚠️ `sections/` içinde BULUNAMADI: " + ", ".join(kayip)]
    satirlar += ["", ONCELIK_BITTI]
    return "\n".join(satirlar)


def blogu_degistir(belge: str, yeni_blok: str, basla: str = BASLA, bitti: str = BITTI,
                   dosya_adi: str = "DURUM-INDEX.md") -> str:
    i, j = belge.find(basla), belge.find(bitti)
    if i < 0 or j < 0:
        raise SystemExit(
            f"{dosya_adi} içinde otomatik blok işaretleri yok. Şu ikisi eklenmelidir:\n"
            f"  {basla}\n  {bitti}"
        )
    return belge[:i] + yeni_blok + belge[j + len(bitti):]


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
        print()
        print(oncelik_metni(kayitlar))
        return 0

    INDEKS.write_text(blogu_degistir(INDEKS.read_text(encoding="utf-8"), blok), encoding="utf-8")
    print(f"DURUM-INDEX.md güncellendi ({len(kayitlar)} madde).")
    BACKLOG.write_text(
        blogu_degistir(BACKLOG.read_text(encoding="utf-8"), oncelik_metni(kayitlar),
                       ONCELIK_BASLA, ONCELIK_BITTI, "backlog.md"),
        encoding="utf-8")
    print(f"backlog.md öncelik bloğu güncellendi ({len(ONCELIKLI_KODLAR)} kod).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
