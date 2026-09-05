"""
NEREDEYİZ? — durumu YAZMAZ, ÖLÇER (BUG #357).

NEDEN VAR
---------
Her oturum "kaldığımız yer" diye elle yazılmış bir bloğu okuyarak başlıyordu. 5 Eylül 2026
gecesi o yaklaşımın bedeli ölçüldü: `sections/DURUM-INDEX.md` 48 gün boyunca yanlış sayılar
taşıdı (*"RULE'da 12 açık"* derken gerçek 0'dı), `perf-smoke-m90.md` 48 gündür
tekrarlanamayan bir bütçe gösterdi, ve dokuz backlog boyutunda **21 madde** bitmiş olduğu
hâlde "açık" göründü.

**Ders (L79): bir belgeyi bayatlamaktan koruyan şey disiplin değil, TÜRETİLMİŞ olmasıdır.**

Bu betik "neredeyiz" sorusunu bir metne değil, ölçüme sorar. Yeni bir oturum buradan başlar:
tek komut, tek ekran, hepsi o an ölçülmüş.

    python scripts/durum_ozeti.py            # tam
    python scripts/durum_ozeti.py --hizli    # ruff ve test sayımını atla (~1 sn)

Hiçbir bölüm diğerini düşürmez: biri ölçülemezse **"ÖLÇÜLEMEDİ"** yazar ve devam eder —
çünkü bilinmeyen sıfır değildir (L45) ve bir aracın sessizce eksik rapor vermesi, bu
projede tekrar eden arıza sınıfıdır.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

# BUG #349 — sunucu olmayan her süreç kendi log dizinine yazar.
os.environ.setdefault("LOG_DIR", "logs/arac")

from scripts.kabuk import git  # noqa: E402


def _yaz(baslik: str, deger: str) -> None:
    print(f"  {baslik:<26} {deger}")


def _guvenli(fn, varsayilan: str = "ÖLÇÜLEMEDİ") -> str:
    try:
        sonuc = fn()
        return varsayilan if sonuc is None else sonuc
    except Exception as e:  # noqa: BLE001 — bir bölümün düşmesi diğerlerini düşürmemeli
        return f"{varsayilan} ({type(e).__name__})"


def _head() -> str:
    return git("rev-parse", "--short=12", "HEAD").stdout.strip()


def _kirli() -> str:
    cikti = git("status", "--porcelain").stdout.strip()
    return "temiz" if not cikti else f"{len(cikti.splitlines())} dosya DEĞİŞMİŞ"


def _arayuz() -> str:
    """Servis edilen arayüz, bugünkü kaynaktan mı derlenmiş?

    BUG #353 (5 Eyl 2026): dağıtım betiği backend'i güncelliyor ama `frontend/dist`'i
    HİÇ derlemiyordu; `dist` üç gün eskiydi ve altı düzeltmenin arayüz yarısı
    kullanıcıya HİÇ ULAŞMAMIŞTI. Betiğe derleme adımı eklendi — ama kimse dağıtmazsa
    yine sessiz kalır. Bu satır o sessizliği bitirir: durum sorulduğunda arayüzün
    bayat olup olmadığı da SÖYLENİR.
    """
    kaynak = git("log", "-1", "--format=%H", "--",
                 "frontend/src", "frontend/package.json",
                 "frontend/vite.config.js", "frontend/index.html").stdout.strip()
    damga_dosyasi = KOK / "frontend" / "dist" / ".kaynak-damgasi"
    index = KOK / "frontend" / "dist" / "index.html"
    if not index.exists():
        return "DERLENMEMİŞ — `npm run build` gerekli"
    if not damga_dosyasi.exists():
        return "damga YOK — bir kez `guncelle.ps1` koşulmalı"
    damga = damga_dosyasi.read_text(encoding="utf-8-sig").strip()
    if damga != kaynak:
        return f"BAYAT — dist {damga[:12]} != kaynak {kaynak[:12]} (`guncelle.ps1`)"
    return f"güncel ({kaynak[:12]})"


def _canli_damga(port: int = 8000) -> str:
    with urllib.request.urlopen(f"http://localhost:{port}/api/meta", timeout=6) as r:
        return json.loads(r.read()).get("build") or "?"


def _backlog() -> str:
    from scripts.backlog_ozeti import ISARET_ANLAMI, maddeler, ozet
    kayitlar = maddeler()
    tablo = ozet(kayitlar)
    toplam = {i: sum(h.get(i, 0) for h in tablo.values()) for i in ISARET_ANLAMI}
    parca = " · ".join(f"{i}{toplam[i]}" for i in sorted(ISARET_ANLAMI) if toplam[i])
    return f"{len(kayitlar)} madde   ({parca})"


def _bayat_belge() -> str:
    p = subprocess.run(  # noqa: S603
        [sys.executable, str(KOK / "scripts" / "belge_denetimi.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(KOK), timeout=180, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    for satir in (p.stdout or "").splitlines():
        if "dokunulmamış" in satir or "dokunulmamis" in satir:
            # Satır: "[RAPOR] ... dokunulmamış: 12  (günlük/arşiv ... muaf tutulan: 149)"
            # Sondan bölmek MUAF sayısını verirdi — aranan, ilk iki nokta üstünden sonraki
            # ilk sayıdır. (Bir ayrıştırma kestirmesi, sessizce yanlış sayı basar.)
            m = re.search(r"dokunulmam[ıi]ş?:?\s*(\d+)", satir)
            if m:
                return f"{m.group(1)} belge"
    return None


def _erisilebilirlik() -> str:
    p = subprocess.run(  # noqa: S603
        [sys.executable, str(KOK / "scripts" / "erisilebilirlik_raporu.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(KOK), timeout=120, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    for satir in (p.stdout or "").splitlines():
        if "ERISILEBILIRLIK:" in satir:
            return satir.split("ERISILEBILIRLIK:", 1)[-1].strip()
    return None


def _kalite() -> str:
    p = subprocess.run(  # noqa: S603
        [sys.executable, str(KOK / "scripts" / "kalite_kapisi.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(KOK), timeout=300, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    aileler = [s.strip() for s in (p.stdout or "").splitlines()
               if s.strip().startswith(("B ", "E9", "F ", "S ", "TOPLAM"))]
    durum = "geçti" if p.returncode == 0 else "KIRIK"
    return f"{durum}   " + " · ".join(" ".join(a.split()[:4]) for a in aileler if a)


def _test_sayisi() -> str:
    p = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "tests/", "-q", "--collect-only",
         "-p", "no:cacheprovider"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(KOK), timeout=300, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    for satir in reversed((p.stdout or "").splitlines()):
        if "tests collected" in satir or "test collected" in satir:
            return satir.strip()
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Projenin BUGÜNKÜ durumunu ölçer.")
    ap.add_argument("--hizli", action="store_true", help="ruff ve test sayımını atla.")
    secenek = ap.parse_args(argv)

    print("NEREDEYİZ — hepsi ŞİMDİ ölçüldü (hiçbiri elle yazılmadı)\n")

    head = _guvenli(_head)
    canli = _guvenli(_canli_damga)
    _yaz("yerel HEAD", head)
    _yaz("canlı damga", canli)
    if head != "ÖLÇÜLEMEDİ" and canli != "ÖLÇÜLEMEDİ":
        _yaz("sürükleme", "0 (canlı = HEAD)" if canli.startswith(head[:12]) else
                          "VAR — `deploy/windows/guncelle.ps1` koşulmalı")
    _yaz("arayüz derlemesi", _guvenli(_arayuz))
    _yaz("çalışma ağacı", _guvenli(_kirli))
    print()
    _yaz("backlog", _guvenli(_backlog))
    _yaz("bayat belge", _guvenli(_bayat_belge))
    _yaz("erişilebilirlik", _guvenli(_erisilebilirlik))
    if not secenek.hizli:
        print()
        _yaz("kalite kapısı", _guvenli(_kalite))
        _yaz("test sayısı", _guvenli(_test_sayisi))
    print("\n  (CI durumu: python -m scripts.ci_durum)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
