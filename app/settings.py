"""
M16 (BUG #157) — Güvenlik config doğrulama + startup fail-fast.

R3 arka plan: SECRET_KEY `app/auth.py:_secret()` içinde okunur; boşsa RuntimeError raise
(fail-closed, evrensel dev-default fallback YOK). Zayıflık: doğrulama LAZY (ilk auth
işleminde, uygulama başlangıcında değil) → `ENVIRONMENT=production` + eksik/zayıf SECRET_KEY
ile deploy boot'ta yakalanmaz, ilk auth isteğinde 500 verir.

Bu modül startup'ta çağrılır (main.py lifespan): production'da güvenlik config sorunu →
RuntimeError (uygulama açılmaz, net hata). Development'ta yalnız warning (çalışmaya devam).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

MIN_SECRET_ENTROPY = 32  # JWT HS256 için makul alt sınır (karakter)


def environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower()


def is_production() -> bool:
    return environment() == "production"


def secret_key_problems() -> list[str]:
    """SECRET_KEY ile ilgili güvenlik sorunlarını döndürür (boş liste = sorun yok)."""
    secret = os.getenv("SECRET_KEY", "").strip()
    problems: list[str] = []
    if not secret:
        problems.append("SECRET_KEY tanımsız/boş")
    elif secret.startswith("dev-default"):
        problems.append("SECRET_KEY 'dev-default' ile başlıyor (production'da yasak)")
    # MA3 (Wave-8): .env.prod.example placeholder'ı git'te herkese açık — operatör değiştirmezse
    # bilinen-secret'la deploy olur. "REPLACE" içeren placeholder'ı reddet (fail-fast).
    elif "REPLACE" in secret:
        problems.append("SECRET_KEY hâlâ .env.prod.example placeholder'ı (REPLACE_...) — gerçek değerle değiştir")
    elif len(secret) < MIN_SECRET_ENTROPY:
        problems.append(f"SECRET_KEY yetersiz entropy (<{MIN_SECRET_ENTROPY} karakter)")
    return problems


def validate_security_config() -> None:
    """Startup fail-fast. Production'da güvenlik config sorunu → RuntimeError; dev'de warning."""
    problems = secret_key_problems()
    if not problems:
        logger.info("[security] config doğrulaması geçti (environment=%s)", environment())
        return

    msg = "Güvenlik config sorunları: " + "; ".join(problems)
    if is_production():
        raise RuntimeError(
            f"[FAIL-FAST] {msg}. Production'da uygulama başlatılamaz — .env'de güçlü SECRET_KEY "
            'ayarla: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    logger.warning("[security] %s (environment=development — uyarı, çalışmaya devam)", msg)
