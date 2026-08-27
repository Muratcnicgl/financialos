r"""
KALİTE KAPISI — GERİLEME SAYACI (BUG #309 / KAP-04).

Felsefe seen-backend'in `quality-baseline.json`'ından alındı: **hedef koyma, GERİLEMEYİ
yakala.** `docs/kalite-seruveni/kalite-baseline.json` bir TAVAN tutar; ölçülen değer tavanı
aşarsa kapı kırılır, altına düşerse tavan aşağı çekilir ve kazanım kilitlenir.

NEDEN HEDEF DEĞİL TAVAN: 27 Ağu 2026'da ölçüldüğünde 291 bulgu vardı ve bunların
**hiçbiri gerçek defekt değildi** (ayrıntılı gerekçe `ruff.toml` başında). "Önce 291'i
temizle" demek, sinyali olmayan devasa bir diff üretip gerçek değişiklikleri gizlerdi.
"Kuralları kapat" demek sinyali tamamen öldürürdü. Üçüncü yol: hepsi görünür kalır, sayı
yukarı çıkamaz, dosyalara dokundukça aşağı iner.

SEEN'İN SAYACINDAN BİR FARK — ARAÇ SÜRÜMÜ KİLİTLİ:
Bir linter sürümü yeni kural ekler ya da mevcut kuralı değiştirir; o an tavan sessizce
anlamını yitirir (sayı zıplarsa sahte kırmızı, düşerse gerçek gerileme görünmez olur).
Bu yüzden baseline aracın sürümünü de tutar ve kapı ÖNCE onu doğrular. `requirements-dev.txt`
`ruff`u tam sürümle sabitler; ikisi ayrışırsa kapı sebebini söyleyerek durur.

Kullanım:
    .\venv\Scripts\python.exe scripts/kalite_kapisi.py            # ölç ve karşılaştır
    .\venv\Scripts\python.exe scripts/kalite_kapisi.py --yaz      # tavanı ölçülene çek

`--yaz` yalnız İYİLEŞMEYİ kilitlemek için kullanılır; tavanı YÜKSELTMEZ. Gerileme
bilinçliyse baseline dosyası ELLE ve gerekçesiyle düzenlenir.

GUNCELLEMELER
-------------
BUG #309 fix: dosya oluşturuldu (KAP-04).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_KOK = Path(__file__).resolve().parent.parent
BASELINE_YOLU = REPO_KOK / "docs" / "kalite-seruveni" / "kalite-baseline.json"

# Bulgu kodunun ailesi: "F401" -> "F", "B904" -> "B", "E902" -> "E9".
# E9 özel: ruff'ta E9xx sözdizimi/derleme hatalarıdır ve diğer E'lerden ayrı tutulur
# (E711/E712 bu projede yanlış alarm — bkz. `ruff.toml`).
_KOD = re.compile(r"^(?P<harf>[A-Z]+)(?P<sayi>\d+)$")


def _aile(kod: str) -> str:
    m = _KOD.match(kod)
    if not m:
        return kod
    harf, sayi = m.group("harf"), m.group("sayi")
    if harf == "E" and sayi.startswith("9"):
        return "E9"
    return harf


def ruff_yolu() -> str:
    """Önce venv'in ruff'u, sonra PATH. Bulunamazsa kapı SESSİZ GEÇMEZ, durur."""
    for aday in (
        REPO_KOK / "venv" / "Scripts" / "ruff.exe",
        REPO_KOK / "venv" / "bin" / "ruff",
    ):
        if aday.exists():
            return str(aday)
    bulunan = shutil.which("ruff")
    if bulunan:
        return bulunan
    raise SystemExit(
        "ruff bulunamadı. Kurulum: pip install -r requirements-dev.txt\n"
        "(Kapı 'araç yok' diye SESSİZCE geçmez — kurulmuşluğu ölçen bir şey yoksa\n"
        " mekanizma sessizce yoktur, L64.)"
    )


def olculen_surum(ruff: str) -> str:
    cikti = subprocess.run([ruff, "--version"], capture_output=True, text=True, check=True)
    # "ruff 0.16.4"
    return cikti.stdout.strip().split()[-1]


def bulgulari_say(ruff: str) -> tuple[Counter, int]:
    """`ruff check .` çıktısını aileye göre sayar. Çıkış kodu 1'dir (bulgu var) — hata değil."""
    sonuc = subprocess.run(
        [ruff, "check", ".", "--no-cache", "--output-format", "concise"],
        cwd=str(REPO_KOK),
        capture_output=True,
        text=True,
    )
    if sonuc.returncode not in (0, 1):
        raise SystemExit(f"ruff beklenmedik çıkış kodu {sonuc.returncode}:\n{sonuc.stderr}")

    sayac: Counter = Counter()
    toplam = 0
    for satir in sonuc.stdout.splitlines():
        # "app\routers\accounts.py:253:9: B904 Within an `except` clause, ..."
        parcalar = satir.split(": ", 1)
        if len(parcalar) != 2 or ":" not in parcalar[0]:
            continue
        kod = parcalar[1].split(" ", 1)[0]
        if not _KOD.match(kod):
            continue
        sayac[_aile(kod)] += 1
        toplam += 1
    return sayac, toplam


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description="Kalite gerileme sayacı.")
    ayristirici.add_argument(
        "--yaz",
        action="store_true",
        help="Tavanı ölçülen değere ÇEK (yalnız iyileşmeyi kilitler; yükseltmez).",
    )
    secenek = ayristirici.parse_args(argv)

    baseline = json.loads(BASELINE_YOLU.read_text(encoding="utf-8"))
    ruff = ruff_yolu()

    # 1) ARAÇ SÜRÜMÜ — tavandan önce bu doğrulanır.
    beklenen = baseline["arac"]["surum"]
    olculen = olculen_surum(ruff)
    if olculen != beklenen:
        print(
            f"ARAÇ SÜRÜMÜ AYRIŞTI: baseline {beklenen}, kurulu {olculen}.\n"
            "Tavan bir sürüme aittir; sürüm değişince sayı anlamını yitirir.\n"
            "Yükseltme bilinçliyse: requirements-dev.txt'i güncelle, süiti koştur,\n"
            "sonra `python scripts/kalite_kapisi.py --yaz` ile tavanı YENİDEN ÖLÇ.",
            file=sys.stderr,
        )
        return 1

    sayac, toplam = bulgulari_say(ruff)
    tavanlar = baseline["tavan"]

    kirildi = False
    iyilesen = False
    satirlar = []
    for aile in sorted(set(tavanlar) | set(sayac)):
        olcum = sayac.get(aile, 0)
        tavan = tavanlar.get(aile)
        if tavan is None:
            durum = "YENİ AİLE — baseline'da yok"
            kirildi = True
        elif olcum > tavan:
            durum = f"GERİLEME (+{olcum - tavan})"
            kirildi = True
        elif olcum < tavan:
            durum = f"İYİLEŞME (-{tavan - olcum}) — tavan indirilmeli"
            iyilesen = True
        else:
            durum = "aynı"
        satirlar.append(f"  {aile:<4} {olcum:>5} / {tavan if tavan is not None else '—':>5}  {durum}")

    print(f"KALİTE KAPISI (ruff {olculen}) — ölçülen / tavan")
    print("\n".join(satirlar))
    print(f"  {'TOPLAM':<4} {toplam:>3}")

    if secenek.yaz:
        if kirildi:
            print(
                "\n--yaz TAVANI YÜKSELTMEZ. Ölçülen değer tavanı aşıyor; bu bir gerilemedir.\n"
                "Düzelt, ya da bilinçli bir kararsa baseline dosyasını ELLE ve gerekçesiyle güncelle.",
                file=sys.stderr,
            )
            return 1
        baseline["tavan"] = {aile: sayac.get(aile, 0) for aile in tavanlar}
        BASELINE_YOLU.write_text(
            json.dumps(baseline, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"\ntavan güncellendi: {BASELINE_YOLU}")
        return 0

    if kirildi:
        print(
            "\nKAPI KIRILDI: ölçülen değer tavanı aştı. Bu bir gerilemedir.\n"
            "Düzelt, ya da bilinçli bir kararsa\n"
            f"  {BASELINE_YOLU.relative_to(REPO_KOK)}\n"
            "dosyasını gerekçesiyle güncelle.",
            file=sys.stderr,
        )
        return 1

    if iyilesen:
        print(
            "\nBULGU SAYISI DÜŞMÜŞ — kazanımı kilitle:\n"
            "  python scripts/kalite_kapisi.py --yaz"
        )

    print("\nkapı geçildi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
