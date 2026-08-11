"""
Sürüm bilgisi (P9 / BUG #200) — tek kaynak.

Sorun: sürüm `app/main.py` içinde `"0.1.0"` olarak SABİT yazılıydı ve hiç güncellenmiyordu.
Canlıda "hangi sürüm koşuyor?" sorusunun cevabı yoktu: bir kullanıcı hata bildirdiğinde
hangi kodun çalıştığı, deploy'un gerçekten güncellenip güncellenmediği, geri alma sonrası
hangi sürüme dönüldüğü **ölçülemiyordu**. Yayın yönetiminin (P9) ön koşuludur.

Sürüm iki parçadan oluşur:
  - `APP_VERSION`  : elle yönetilen anlamlı sürüm (CHANGELOG.md ile aynı).
  - `BUILD_COMMIT` : çalışan kodun git kimliği.

BUG #294 fix (11 Ağu 2026) — DAMGA YALAN SÖYLÜYORDU. `build_commit()` YALNIZ
`BUILD_COMMIT` env değişkenine bakıyordu ve o değişken `.env`'de **elle** tutuluyordu.
Bu makinedeki kapalı beta "git pull + yeniden başlat" ile güncelleniyor; kimse `.env`'i
elle düzeltmediği için damga deploy'dan deploy'a donuyor. Ölçüm: canlı uç
`build: 6d3bf26abd62` derken çalışan kod `fc10e0b`di — yani sürüm damgası, var olmasının
TEK sebebi olan soruya (hangi kod koşuyor?) **yanlış** cevap veriyordu. Kullanıcı hata
bildirdiğinde yanlış commit'e bakılırdı.

Öncelik artık tersine: **önce çalışma kopyasının git'i, sonra env**. Gerekçe — bir git
çalışma kopyasından koşan süreç için gerçeği `.git` bilir, env yalnızca bir iddiadır.
Konteyner imajında `.git` bulunmaz; orada env doğru kaynaktır (imaj build'inde enjekte
edilir) ve fallback olarak kalır.

Sonuç süreç ömrü boyunca bir kez hesaplanır: `git` çağrısı her istekte yapılamaz (sağlık
ucu sıcak yoldur) ve zaten çalışan kod süreç boyunca değişmez — dosyalar değişse bile
belleğe yüklenmiş modüller aynıdır, damganın söylemesi gereken de budur.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

APP_VERSION = "0.2.0"   # CHANGELOG.md ile SENKRON olmalı (testle kilitli)

_KOK = Path(__file__).resolve().parent.parent


def _git_commit() -> str:
    """Çalışma kopyasının HEAD SHA'sı; git yoksa/başarısızsa boş string.

    Kirli çalışma kopyası `+` ile işaretlenir: "abc123def456+" — canlıda commit
    edilmemiş değişiklikle koşmak, o commit'i koşmakla aynı şey DEĞİLDİR.
    """
    if not (_KOK / ".git").exists():
        return ""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_KOK, capture_output=True,
            text=True, timeout=5,
        )
        if sha.returncode != 0:
            return ""
        kimlik = sha.stdout.strip()[:12]
        if not kimlik:
            return ""
        kirli = subprocess.run(
            ["git", "status", "--porcelain"], cwd=_KOK, capture_output=True,
            text=True, timeout=5,
        )
        if kirli.returncode == 0 and kirli.stdout.strip():
            kimlik += "+"
        return kimlik
    except (OSError, subprocess.SubprocessError):
        return ""   # git yok / bozuk repo — damga sessizce env'e düşer


@lru_cache(maxsize=1)
def build_commit() -> str:
    """Çalışan kodun kimliği: git çalışma kopyası > env > 'bilinmiyor'.

    Kesme uzunluğu 12: `_git_commit()` zaten 12 karaktere kısaltır ve kirli kopyada
    13. karakter olarak `+` ekler — o değer burada bir daha kesilmez. Env yolu (konteyner)
    ham bir SHA taşır ve 12'ye iner.
    """
    return _git_commit() or (os.getenv("BUILD_COMMIT", "").strip() or "bilinmiyor")[:12]


def full_version() -> str:
    return f"{APP_VERSION} ({build_commit()})"
