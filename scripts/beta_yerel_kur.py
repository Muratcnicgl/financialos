"""
Kapalı beta — YEREL (Docker'sız) kurulum yapılandırıcısı.  # BUG #285 / B4

Ne yapar: `.env` dosyasına kapalı betanın gerektirdiği anahtarları ekler/günceller.
Ne YAPMAZ: hiçbir sır değerini ekrana basmaz, mevcut anahtarları silmez, yedeksiz yazmaz.

NEDEN BU SCRIPT VAR — ölçülen iki SESSİZ tehlike:

  1. **`ENVIRONMENT` tanımsızsa kapalı beta AÇIKTIR.** `beta_access.registration_mode()`
     production değilse varsayılan olarak **"open"** döner. Yani uygulamayı olduğu gibi
     yayınlarsan adresi bilen herkes kayıt olabilir — BUG #199'un tam olarak engellemek
     için yazıldığı durum, yalnızca bir env değişkeni eksik diye geri gelir. Bu script
     hem `ENVIRONMENT=production` hem de AÇIKÇA `REGISTRATION_MODE=invite_only` yazar
     (iki katman: birinin varsayılanına güvenilmez).

  2. **`FRONTEND_URL` / `OAUTH_REDIRECT_BASE` localhost kalırsa** şifre sıfırlama
     e-postaları ve Google/GitHub yönlendirmeleri **davetlinin ulaşamayacağı** bir adrese
     gider. Hata mesajı vermez; kullanıcı tıklar ve hiçbir şey olmaz.

Kullanım:
    python -m scripts.beta_yerel_kur --url https://financialos.tailXXXX.ts.net \\
                                     --destek eposta@ornek.com
    python -m scripts.beta_yerel_kur --url ... --destek ... --uygula   # gerçekten yaz

`--uygula` verilmezse yalnız NE DEĞİŞECEĞİNİ gösterir (kuru koşum).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
ENV = KOK / ".env"

# Değeri SIR olmayan, güvenle gösterilebilen anahtarlar (rapor bunları açık yazar).
GORUNUR = {"ENVIRONMENT", "REGISTRATION_MODE", "SERVE_SPA", "BUILD_COMMIT",
           "FRONTEND_URL", "OAUTH_REDIRECT_BASE", "SUPPORT_EMAIL", "AUTH_ENABLED"}


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=KOK,
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def _mevcut(metin: str) -> dict[str, str]:
    d = {}
    for satir in metin.splitlines():
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", satir)
        if m:
            d[m.group(1)] = m.group(2).strip()
    return d


def _yaz(metin: str, anahtar: str, deger: str) -> str:
    """Anahtar varsa yerinde günceller, yoksa sona ekler (yorum satırları korunur)."""
    desen = re.compile(rf"^(\s*{re.escape(anahtar)}\s*=).*$", re.MULTILINE)
    if desen.search(metin):
        return desen.sub(lambda m: f"{m.group(1)}{deger}", metin, count=1)
    ayrac = "" if metin.endswith("\n") else "\n"
    return f"{metin}{ayrac}{anahtar}={deger}\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Kapalı beta yerel kurulum yapılandırıcısı")
    ap.add_argument("--url", required=True,
                    help="Davetlilerin göreceği tam adres, örn. https://x.tailABC.ts.net")
    ap.add_argument("--destek", required=True,
                    help="SUPPORT_EMAIL — giriş YAPAMAYAN kullanıcının tek kanalı")
    ap.add_argument("--uygula", action="store_true", help="Gerçekten yaz (yoksa kuru koşum)")
    a = ap.parse_args()

    url = a.url.rstrip("/")
    if not url.startswith("https://"):
        print(f"HATA: adres https:// ile başlamalı (verilen: {url})")
        return 2
    if "@" not in a.destek:
        print(f"HATA: --destek geçerli bir e-posta değil: {a.destek}")
        return 2

    if not ENV.exists():
        print(f"HATA: {ENV} yok. Önce .env.example'dan bir .env oluşturun.")
        return 2

    metin = ENV.read_text(encoding="utf-8")
    onceki = _mevcut(metin)

    hedef = {
        # 1. TEHLİKE: bu ikisi olmadan kapalı beta AÇIK olur.
        "ENVIRONMENT": "production",
        "REGISTRATION_MODE": "invite_only",
        # 2. TEHLİKE: bu ikisi localhost kalırsa e-posta/OAuth bağlantıları ölü olur.
        "FRONTEND_URL": url,
        "OAUTH_REDIRECT_BASE": url,
        # production fail-fast bunu ŞART koşar (giriş yapamayanın tek kanalı, BUG #210).
        "SUPPORT_EMAIL": a.destek,
        # nginx yok → arayüzü uygulama servis eder (BUG #284).
        "SERVE_SPA": "1",
        # "hangi kod koşuyor" sorusunun cevabı (BUG #200); geri bildirime de yazılır (#281).
        "BUILD_COMMIT": _git_sha(),
        # production'da zaten şart; açıkça yazıyoruz ki kimse varsayılana güvenmesin.
        "AUTH_ENABLED": "true",
    }
    hedef = {k: v for k, v in hedef.items() if v}

    degisecek = {k: v for k, v in hedef.items() if onceki.get(k, "") != v}

    print("=" * 72)
    print("KAPALI BETA — YEREL KURULUM")
    print("=" * 72)
    print(f"Adres      : {url}")
    print(f"Destek     : {a.destek}")
    print(f"Build      : {hedef.get('BUILD_COMMIT', '(git yok)')}")
    print()
    if not degisecek:
        print("Değişiklik YOK — .env zaten hedef durumda.")
    else:
        print("Değişecek anahtarlar:")
        for k, v in degisecek.items():
            eski = onceki.get(k)
            eski_g = (eski if k in GORUNUR else "***") if eski else "(yok)"
            yeni_g = v if k in GORUNUR else "***"
            print(f"  {k:<22} {eski_g}  →  {yeni_g}")

    # Sır anahtarları YALNIZ varlık olarak denetlenir; değerleri hiç okunmaz/yazılmaz.
    eksik_sir = [k for k in ("SECRET_KEY",) if not onceki.get(k)]
    if eksik_sir:
        print()
        print("!! EKSİK SIR: " + ", ".join(eksik_sir))
        print('   Üret: python -c "import secrets; print(secrets.token_urlsafe(48))"')
        print("   ve .env'e kendin ekle — bu script sır ÜRETMEZ/YAZMAZ.")

    if not a.uygula:
        print()
        print("KURU KOŞUM — hiçbir şey yazılmadı. Uygulamak için: --uygula")
        return 0

    if degisecek:
        yedek = ENV.with_suffix(f".env.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(ENV, yedek)
        for k, v in hedef.items():
            metin = _yaz(metin, k, v)
        ENV.write_text(metin, encoding="utf-8")
        print()
        print(f"YAZILDI. Yedek: {yedek.name}")

    print()
    print("SIRADAKİ ELLE ADIMLAR (bunları script yapamaz):")
    print(f"  1. Google Cloud Console → OAuth istemcisine yetkili yönlendirme URI'si ekle:")
    print(f"     {url}/api/auth/callback/google")
    print(f"  2. GitHub → OAuth App → Authorization callback URL:")
    print(f"     {url}/api/auth/callback/github")
    print("     (bunlar eklenmezse sosyal giriş davetlide SESSİZCE kırılır)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
