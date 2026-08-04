"""
Sürüm bilgisi (P9 / BUG #200) — tek kaynak.

Sorun: sürüm `app/main.py` içinde `"0.1.0"` olarak SABİT yazılıydı ve hiç güncellenmiyordu.
Canlıda "hangi sürüm koşuyor?" sorusunun cevabı yoktu: bir kullanıcı hata bildirdiğinde
hangi kodun çalıştığı, deploy'un gerçekten güncellenip güncellenmediği, geri alma sonrası
hangi sürüme dönüldüğü **ölçülemiyordu**. Yayın yönetiminin (P9) ön koşuludur.

Sürüm iki parçadan oluşur:
  - `APP_VERSION`  : elle yönetilen anlamlı sürüm (CHANGELOG.md ile aynı).
  - `BUILD_COMMIT` : deploy'da enjekte edilen git SHA (env: `BUILD_COMMIT`).
Böylece "0.2.0 (a1b2c3d)" gibi kesin bir kimlik doğar.
"""
from __future__ import annotations

import os

APP_VERSION = "0.2.0"   # CHANGELOG.md ile SENKRON olmalı (testle kilitli)


def build_commit() -> str:
    """Deploy sırasında enjekte edilen git SHA (yoksa 'bilinmiyor')."""
    return (os.getenv("BUILD_COMMIT", "").strip() or "bilinmiyor")[:12]


def full_version() -> str:
    return f"{APP_VERSION} ({build_commit()})"
