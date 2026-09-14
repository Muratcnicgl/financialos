r"""
FRONTEND LİNT KAPISI — ESLint GERİLEME SAYACI (BUG #474 / DEVOPS-003).

`scripts/kalite_kapisi.py`'nin (ruff) frontend eşi; felsefe aynı: **hedef koyma, GERİLEMEYİ
yakala.** ESLint `error` seviyesindeki her bulgu kapıyı kırar (bunlar sıfırlandı ve sıfır
kalır). `warn` seviyesindeki kurallar TAVANLIDIR: `docs/kalite-seruveni/kalite-baseline.json`
› `frontend.tavan` kural başına bir sayı tutar; ölçülen tavanı aşarsa kapı kırılır, altına
düşerse `--yaz` tavanı aşağı çeker ve kazanım kilitlenir.

NEDEN KURAL BAŞINA: tek toplam takas yapmaya izin verir (bir yerde düzelt, başka kuralda
gerile, sayı aynı kalsın). Kural başına tavanda her kuralın artışı kendi başına kırar.

ARAÇ SÜRÜMÜ KİLİTLİ: baseline eslint sürümünü tutar; `frontend/package.json` tam sürümle
sabitler (`9.39.5`); kapı ÖNCE bunu doğrular — yeni sürüm kural ekler/değiştirir, o an tavan
anlamını yitirir.

ÖLÇÜM: `node scripts/lint.cjs -f json` (frontend içinde). Sarmalayıcı, Windows'ta "İ" içeren
yollarda ESLint ignore eşleştirmesinin bozulmasına karşı 8.3 kısa yola düşer (gerekçe dosyada).

Kullanım:
    python scripts/eslint_kapisi.py            # ölç ve karşılaştır
    python scripts/eslint_kapisi.py --yaz      # tavanı ölçülene çek (yalnız iyileşme)
    python scripts/eslint_kapisi.py --dosya X  # hazır JSON raporu üzerinden karar (test/CI)

GUNCELLEMELER
-------------
BUG #474 fix: dosya oluşturuldu (DEVOPS-003).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_KOK = Path(__file__).resolve().parent.parent
FRONTEND = REPO_KOK / "frontend"
BASELINE_YOLU = REPO_KOK / "docs" / "kalite-seruveni" / "kalite-baseline.json"


def kurulu_surum() -> str:
    paket = FRONTEND / "node_modules" / "eslint" / "package.json"
    if not paket.exists():
        raise SystemExit(
            "frontend/node_modules/eslint yok. Kurulum: (cd frontend && npm ci)\n"
            "(Kapı 'araç yok' diye SESSİZCE geçmez — L64.)"
        )
    return json.loads(paket.read_text(encoding="utf-8"))["version"]


def raporu_uret() -> list[dict]:
    node = shutil.which("node")
    if not node:
        raise SystemExit("node bulunamadı; frontend lint kapısı ölçemez.")
    sonuc = subprocess.run(  # noqa: S603 — sabit komut, kullanıcı girdisi yok
        [node, "scripts/lint.cjs", "-f", "json"],
        cwd=str(FRONTEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    # ESLint: 0 = temiz, 1 = bulgu var, 2 = yapılandırma/çalışma hatası.
    if sonuc.returncode not in (0, 1):
        raise SystemExit(f"eslint beklenmedik çıkış kodu {sonuc.returncode}:\n{sonuc.stderr}")
    # stdout'un başında sarmalayıcı gürültüsü olabilir; JSON '[' ile başlar.
    ham = sonuc.stdout[sonuc.stdout.find("[") :]
    return json.loads(ham)


def say(rapor: list[dict]) -> tuple[list[str], Counter]:
    """(hata satırları, kural başına uyarı sayacı)."""
    hatalar: list[str] = []
    uyarilar: Counter = Counter()
    for dosya in rapor:
        ad = Path(dosya["filePath"]).as_posix().split("/frontend/", 1)[-1]
        for m in dosya.get("messages", []):
            kural = m.get("ruleId") or "(kuralsız)"
            if m.get("severity") == 2:
                hatalar.append(f"  {ad}:{m.get('line')} {kural} {m.get('message', '')[:90]}")
            else:
                uyarilar[kural] += 1
    return hatalar, uyarilar


def karar(baseline: dict, rapor: list[dict], surum: str, yaz: bool) -> int:
    fe = baseline["frontend"]
    beklenen = fe["arac"]["surum"]
    if surum != beklenen:
        print(
            f"ARAÇ SÜRÜMÜ AYRIŞTI: baseline eslint {beklenen}, kurulu {surum}.\n"
            "Tavan bir sürüme aittir. Yükseltme bilinçliyse: frontend/package.json'ı güncelle,\n"
            "süiti koştur, sonra `python scripts/eslint_kapisi.py --yaz` ile tavanı YENİDEN ÖLÇ.",
            file=sys.stderr,
        )
        return 1

    hatalar, uyarilar = say(rapor)
    tavanlar: dict[str, int] = fe["tavan"]
    kirildi = bool(hatalar)
    iyilesen = False
    satirlar = []
    for kural in sorted(set(tavanlar) | set(uyarilar)):
        olcum = uyarilar.get(kural, 0)
        tavan = tavanlar.get(kural)
        if tavan is None:
            durum = "YENİ KURAL — baseline'da yok"
            kirildi = True
        elif olcum > tavan:
            durum = f"GERİLEME (+{olcum - tavan})"
            kirildi = True
        elif olcum < tavan:
            durum = f"İYİLEŞME (-{tavan - olcum}) — tavan indirilmeli"
            iyilesen = True
        else:
            durum = "aynı"
        satirlar.append(f"  {kural:<38} {olcum:>4} / {tavan if tavan is not None else '—':>4}  {durum}")

    print(f"FRONTEND LİNT KAPISI (eslint {surum}) — uyarı: ölçülen / tavan")
    print("\n".join(satirlar))
    print(f"  {'HATA':<38} {len(hatalar):>4} /    0  {'GERİLEME' if hatalar else 'aynı'}")
    if hatalar:
        print("\n".join(hatalar[:40]))

    if yaz:
        if kirildi:
            print(
                "\n--yaz TAVANI YÜKSELTMEZ ve hata varken yazmaz. Düzelt, ya da bilinçli bir kararsa\n"
                "baseline dosyasını ELLE ve gerekçesiyle güncelle.",
                file=sys.stderr,
            )
            return 1
        fe["tavan"] = {kural: uyarilar.get(kural, 0) for kural in tavanlar}
        BASELINE_YOLU.write_text(
            json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\ntavan güncellendi: {BASELINE_YOLU}")
        return 0

    if kirildi:
        print(
            "\nKAPI KIRILDI: hata var ya da uyarı tavanı aşıldı. Bu bir gerilemedir.\n"
            f"Düzelt, ya da bilinçli bir kararsa {BASELINE_YOLU.relative_to(REPO_KOK)} dosyasını gerekçesiyle güncelle.",
            file=sys.stderr,
        )
        return 1
    if iyilesen:
        print("\nUYARI SAYISI DÜŞMÜŞ — kazanımı kilitle:\n  python scripts/eslint_kapisi.py --yaz")
    print("\nkapı geçildi.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description="Frontend lint gerileme sayacı.")
    ayristirici.add_argument("--yaz", action="store_true", help="Tavanı ölçülen değere ÇEK (yalnız iyileşme).")
    ayristirici.add_argument("--dosya", type=Path, help="Hazır ESLint JSON raporu (ölçmek yerine oku).")
    ayristirici.add_argument("--surum", help="Test için: kurulu eslint sürümü yerine bu değeri kullan.")
    secenek = ayristirici.parse_args(argv)

    baseline = json.loads(BASELINE_YOLU.read_text(encoding="utf-8"))
    surum = secenek.surum or kurulu_surum()
    rapor = json.loads(secenek.dosya.read_text(encoding="utf-8")) if secenek.dosya else raporu_uret()
    return karar(baseline, rapor, surum, secenek.yaz)


if __name__ == "__main__":
    raise SystemExit(main())
