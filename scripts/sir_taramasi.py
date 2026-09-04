"""
SIR TARAMASI (SEC-018 / BUG #261) — repoda ve GİT GEÇMİŞİNDE sızmış anahtar var mı.

NEDEN
-----
`.gitignore` doğru olabilir ve yine de bir sır sızmış olabilir: tek bir `git add -f`,
bir yapılandırma örneğine yapıştırılmış gerçek anahtar, ya da silinmiş ama **geçmişte
duran** bir dosya yeter. `.env`'in bugün izlenmiyor olması, dün izlenmediğini kanıtlamaz —
ve git geçmişi silinmez: repo bir gün herkese açılırsa geçmişteki anahtar da açılır.

Backlog SEC-018 bu yüzden "sızma denetimi YAP" diyordu ve kanıtı yoktu ("gitleaks kanıtı yok").
Bu script o kanıtı üretir; CI haftalık koşar.

KULLANIM
--------
    python -m scripts.sir_taramasi              # çalışma ağacı (izlenen dosyalar)
    python -m scripts.sir_taramasi --gecmis     # TÜM git geçmişi (yavaş, CI/haftalık)

Çıkış kodu: 0 temiz · 2 bulgu var (CI'yı kırar).

YANLIŞ-POZİTİF SINIRI (bilinçli)
--------------------------------
Test fixture'ları gerçek anahtar şekilleri kullanır (maskeleme testleri bunsuz yazılamaz).
Onlar `# secret-ornek:` işaretiyle muaf tutulur — muafiyet SESSİZ değildir, işaret gerekir.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

# Anahtarın ŞEKLİ (etiketi değil) — `app/error_tracking.py` ile aynı aile.
DESENLER: list[tuple[str, re.Pattern[str]]] = [
    ("Google/Gemini", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("OpenAI/OpenRouter/Cerebras", re.compile(r"\b(?:sk|csk|rk)-[A-Za-z0-9_\-]{24,}")),
    ("Groq", re.compile(r"\bgsk_[A-Za-z0-9_\-]{24,}")),
    ("Brevo SMTP", re.compile(r"\bxsmtpsib-[A-Za-z0-9_\-]{24,}")),
    ("Anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{24,}")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("Özel anahtar", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    # URL içinde kimlik: bilinçli olarak DAR. İlk sürüm `://kullanici:parola@` deseniyle
    # yazılmıştı ve 13 yanlış-pozitif üretti — CI'daki `postgres:postgres@localhost`,
    # maskeleyicinin KENDİ regex'i, runbook örnekleri… Gürültü üreten kapı ciddiye alınmaz
    # (L22): parola en az 10 karakter olmalı, yer-tutucu sözlüğünde bulunmamalı ve host
    # yerel/örnek olmamalı.
    ("URL içinde kimlik", re.compile(
        r"[a-z][a-z0-9+.\-]*://[^:/\s@]+:(?!(?:postgres|password|parola|sifre|changeme|"
        r"secret|user|test|demo|example|xxx+|<[^>]+>|\$\{|REPLACE|CHANGE|YOUR_|TODO)[^@]*@)"
        r"[^@/\s]{10,}@(?!localhost|127\.0\.0\.1|example\.|.*\.example)")),
]

MUAFIYET_ISARETI = "secret-ornek:"
# Bu yollar tarama dışıdır (üretilen/dış içerik).
ATLA = ("node_modules/", "venv/", "dist/", ".git/", "__pycache__/", "playwright-report/")


def izlenen_dosyalar() -> list[str]:
    """Depoda İZLENEN tüm yollar (üretilen/dış içerik hariç — bkz. `ATLA`).

    Public: `tests/test_depo_kisisel_veri_kapisi.py` de aynı listeyi ister ve
    `git ls-files`'ı BEŞİNCİ kez yeniden yazmasın diye buradan alır. Her yeni kopya
    ruff'ta bir `S607` daha üretiyor ve tavanı yükseltiyordu; `olu_kod_kapisi.izlenen_py`
    ile aynı desen (o `.py`, bu HEPSİ).
    """
    cikti = subprocess.run(["git", "ls-files"], cwd=KOK, capture_output=True, text=True).stdout
    return [s for s in cikti.splitlines() if s and not s.startswith(ATLA)]


def _satir_muaf(satir: str, onceki: str = "") -> bool:
    """İşaret aynı satırda VEYA hemen üstündeki satırda olabilir (uzun satırlar için)."""
    return MUAFIYET_ISARETI in satir or MUAFIYET_ISARETI in onceki


def _baseline() -> set[str]:
    """
    Kabul edilmiş GEÇMİŞ bulguları (yol@sha:satır). Geçmiş yeniden yazılamaz: markerları
    sonradan eklenen test dosyalarının ESKİ blob'ları sonsuza dek eşleşir. Gerçek sızıntıyı
    gizlememek için liste GEREKÇELİDİR ve yalnız `[gecmis]` bulgularına uygulanır.
    """
    yol = KOK / "scripts" / "sir_taramasi_baseline.txt"
    if not yol.exists():
        return set()
    kabul = set()
    for s in yol.read_text(encoding="utf-8").splitlines():
        s = s.strip()
        if not s or s.startswith("#"):
            continue
        kabul.add(s.split("#", 1)[0].strip())
    return kabul


def tara_calisma_agaci() -> list[str]:
    bulgular: list[str] = []
    for rel in izlenen_dosyalar():
        yol = KOK / rel
        try:
            metin = yol.read_text(encoding="utf-8", errors="ignore")
        except (OSError, IsADirectoryError):
            continue
        satirlar = metin.splitlines()
        for i, satir in enumerate(satirlar, 1):
            if _satir_muaf(satir, satirlar[i - 2] if i >= 2 else ""):
                continue
            for ad, desen in DESENLER:
                if desen.search(satir):
                    bulgular.append(f"{rel}:{i}: {ad}")
                    break
    return bulgular


def tara_gecmis() -> list[str]:
    """
    TÜM geçmişteki blob'ları gezer (silinmiş dosyalar dahil).

    Blob başına `git cat-file -p` çalıştırmak Windows'ta dakikalarca sürüyordu (ölçüldü:
    10 dk+ ve bitmedi). `--batch` ile TEK süreç kullanılır: git nesneleri stdin'den okur,
    stdout'a akıtır. Kapının koşulmayacak kadar yavaş olması, kapının olmaması demektir.
    """
    bulgular: list[str] = []
    liste = subprocess.run(["git", "rev-list", "--objects", "--all"],
                           cwd=KOK, capture_output=True, text=True).stdout.splitlines()
    hedefler: list[tuple[str, str]] = []
    for satir in liste:
        parcalar = satir.split(" ", 1)
        if len(parcalar) != 2:
            continue
        sha, yol = parcalar
        if yol.startswith(ATLA) or yol.endswith((".png", ".jpg", ".ico", ".webp", ".pdf", ".db")):
            continue
        hedefler.append((sha, yol))

    if not hedefler:
        return []

    kabul = _baseline()
    proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=KOK,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    girdi = "\n".join(sha for sha, _ in hedefler) + "\n"
    ham, _ = proc.communicate(girdi.encode())

    # Çıktı biçimi: "<sha> <tip> <boyut>\n<icerik>\n" — sırayla ayrıştırılır.
    imlec = 0
    for sha, yol in hedefler:
        satir_sonu = ham.find(b"\n", imlec)
        if satir_sonu == -1:
            break
        baslik = ham[imlec:satir_sonu].decode("utf-8", "ignore").split()
        if len(baslik) < 3:
            imlec = satir_sonu + 1
            continue
        boyut = int(baslik[2])
        govde = ham[satir_sonu + 1: satir_sonu + 1 + boyut]
        imlec = satir_sonu + 1 + boyut + 1
        if boyut > 2_000_000:
            continue
        gsatirlar = govde.decode("utf-8", "ignore").splitlines()
        for i, s in enumerate(gsatirlar, 1):
            if _satir_muaf(s, gsatirlar[i - 2] if i >= 2 else ""):
                continue
            for ad, desen in DESENLER:
                if desen.search(s):
                    anahtar = f"{yol}@{sha[:8]}:{i}"
                    if anahtar in kabul:
                        continue
                    bulgular.append(f"[gecmis] {anahtar}: {ad}")
                    break
    return bulgular


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Repo/gecmis sir taramasi (SEC-018)")
    ap.add_argument("--gecmis", action="store_true", help="tum git gecmisini tara (yavas)")
    args = ap.parse_args(argv)

    bulgular = tara_gecmis() if args.gecmis else tara_calisma_agaci()
    kapsam = "git gecmisi (tum bloblar)" if args.gecmis else "calisma agaci (izlenen dosyalar)"

    if bulgular:
        print(f"KIRMIZI: {len(bulgular)} olasi sir izi ({kapsam}):")
        for b in bulgular[:50]:
            print("  " + b)
        if len(bulgular) > 50:
            print(f"  ... (+{len(bulgular) - 50})")
        print("\nGercekse: anahtari HEMEN iptal et/rotasyona sok, sonra gecmisi temizle.")
        return 2

    print(f"TEMIZ: sir izi yok ({kapsam}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
