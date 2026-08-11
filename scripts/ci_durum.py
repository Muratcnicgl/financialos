"""
CI DURUMU — "uzakta ne oldu?" sorusunun tek komutluk cevabı.

NEDEN VAR (BUG #295-#300 turunun asıl dersi): GitHub Actions **30+ koşum boyunca
kırmızıydı** ve bu hiç fark edilmedi. Yerelde her şey yeşildi, pre-commit her commit'te
süiti koşuyordu — ama uzaktaki kapılar (postgres dual-dialect, e2e, bağımlılık taraması)
günlerce ölüydü. Kırmızı normalleşince yeni bir kırmızı da görünmez olur; BUG #293'ün
ölü e2e testi tam bu yüzden aylarca saklandı.

Yerel süitin yeşil olması CI'ın yeşil olduğu anlamına GELMEZ: CI farklı işletim sistemi,
farklı Node/npm sürümü, `.env` YOKLUĞU ve gerçek bir PostgreSQL servisi ile koşar. Bu
turda bulunan altı defektin dördü yalnızca orada görünüyordu.

Kullanım:
    .\\venv\\Scripts\\python.exe -m scripts.ci_durum            # son koşum
    .\\venv\\Scripts\\python.exe -m scripts.ci_durum --son 10   # son 10 koşumun şeridi
    .\\venv\\Scripts\\python.exe -m scripts.ci_durum --sessiz   # yalnız kırmızıysa yaz

Çıkış kodu: 0 yeşil/bilinmiyor · 1 kırmızı (hook'tan çağrılabilir).
"""
from __future__ import annotations

# Windows konsolu cp1254'tur; bu arac bir CIKTI KARAKTERI yuzunden cokmemeli
# (kendisi bir gorunurluk araci — sessiz kalmasi da cokmesi de kabul edilemez).
import io as _io
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(errors="replace")

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "Muratcnicgl/financialos"
API = f"https://api.github.com/repos/{REPO}/actions"


def _token() -> str | None:
    """git credential deposundan GitHub token'ı (varsa) — özel repo/log erişimi için."""
    try:
        p = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                           capture_output=True, text=True, timeout=10)
        for satir in p.stdout.splitlines():
            if satir.startswith("password="):
                return satir.split("=", 1)[1].strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _iste(yol: str) -> dict | None:
    istek = urllib.request.Request(yol, headers={"Accept": "application/vnd.github+json"})
    tok = _token()
    if tok:
        istek.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(istek, timeout=20) as cevap:
            return json.load(cevap)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None   # ağ yok / kota — bu araç asla akışı durdurmaz


def _kirmizi_adimlar(run_id: int) -> list[str]:
    d = _iste(f"{API}/runs/{run_id}/jobs") or {}
    satirlar = []
    for j in d.get("jobs", []):
        if j.get("conclusion") == "failure":
            satirlar.append(f"  x {j['name']}")
            for s in j.get("steps", []):
                if s.get("conclusion") not in ("success", "skipped", None):
                    satirlar.append(f"      adım: {s['name']}")
    return satirlar


def main() -> int:
    ap = argparse.ArgumentParser(description="Son CI koşum(lar)ının durumu")
    ap.add_argument("--son", type=int, default=1, help="kaç koşum listelensin")
    ap.add_argument("--sessiz", action="store_true", help="yalnız kırmızıysa çıktı ver")
    a = ap.parse_args()

    d = _iste(f"{API}/runs?per_page={max(a.son, 1)}")
    if not d or not d.get("workflow_runs"):
        if not a.sessiz:
            print("[ci] durum okunamadı (ağ yok ya da erişim kapalı) — akış etkilenmez.")
        return 0

    kosumlar = d["workflow_runs"]
    son = kosumlar[0]
    kirmizi = son.get("conclusion") == "failure"

    if a.sessiz and not kirmizi:
        return 0

    if a.son > 1:
        serit = " ".join("K" if r.get("conclusion") == "failure"
                         else ("Y" if r.get("conclusion") == "success" else "?")
                         for r in kosumlar)
        print(f"[ci] son {len(kosumlar)} koşum (yeni-eski): {serit}")

    durum = son.get("conclusion") or son.get("status")
    isaret = "KIRMIZI" if kirmizi else ("YESIL" if durum == "success" else str(durum).upper())
    print(f"[ci] {isaret} · {son['head_sha'][:8]} · {son['display_title'][:60]}")
    print(f"     {son['html_url']}")

    if kirmizi:
        for satir in _kirmizi_adimlar(son["id"]):
            print(satir)
        print("     Yerel süitin yeşil olması CI'ın yeşil olduğu anlamına gelmez:")
        print("     CI farklı OS/Node sürümü, `.env` YOKLUĞU ve gerçek PostgreSQL ile koşar.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
