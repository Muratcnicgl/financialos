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


# FEAT-031: "güvenli borç ödemesi" için varsayılan acil-durum tamponu (TL). Ayarlanabilir —
# projekte nakitin en düşük noktasında dokunulmadan kalması istenen taban. Cockpit senaryoları
# {0, bu değer, 5000} tamponları için ödenebilir tutarı sunar; bu yalnız VARSAYILAN/önerilendir.
def safe_debt_buffer() -> float:
    raw = os.getenv("SAFE_DEBT_BUFFER", "2000").strip()
    try:
        val = float(raw)
        return val if val >= 0 else 2000.0  # negatif anlamsız → varsayılana dön
    except ValueError:
        logger.warning("[settings] geçersiz SAFE_DEBT_BUFFER=%r → varsayılan 2000", raw)
        return 2000.0


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


def auth_problems() -> list[str]:
    """BUG #171 (P2): production'da kimlik doğrulama KAPALI olamaz.

    `AUTH_ENABLED` varsayılanı KAPALI (geriye-uyum, tek-kullanıcı yerel kurulum). Bu değişken
    unutulursa `ENVIRONMENT=production` instance'ı TÜM API'yi kimliksiz "ilk kullanıcı"ya
    açar (cockpit, hesaplar, KVKK export'u, hesap silme). Compose dosyası set ediyor ama
    systemd/manuel `docker run`/PaaS yollarında hiçbir koruma yoktu → startup'ta fail-fast.
    """
    from app import auth as _auth
    if is_production() and not _auth.auth_enabled():
        return ["AUTH_ENABLED production'da açık olmalı (aksi halde API kimliksiz erişime açılır)"]
    return []


def support_problems() -> list[str]:
    """BUG #210 (P8): production'da DESTEK KANALI tanımsız olamaz.

    Giriş yapamayan kullanıcı (yanlış şifre / doğrulanmamış e-posta / davet kodu
    çalışmıyor) uygulama-içi geri bildirim widget'ına da ulaşamaz — geriye tek kanal
    olarak destek adresi kalır. Tanımsızsa kullanıcı sessizce kaybedilir ve KVKK'nın
    "veri sorumlusuna başvuru" hakkı fiilen kullanılamaz hale gelir.
    """
    if not is_production():
        return []
    adres = os.getenv("SUPPORT_EMAIL", "").strip()
    if not adres:
        return ["SUPPORT_EMAIL tanımlı olmalı (giriş yapamayan kullanıcının tek kanalı)"]
    if "@" not in adres:
        return [f"SUPPORT_EMAIL geçerli bir e-posta değil: {adres!r}"]
    return []


def validate_security_config() -> None:
    """Startup fail-fast. Production'da güvenlik config sorunu → RuntimeError; dev'de warning."""
    problems = secret_key_problems() + auth_problems() + support_problems()
    if not problems:
        logger.info("[security] config doğrulaması geçti (environment=%s)", environment())
        return

    msg = "Güvenlik config sorunları: " + "; ".join(problems)
    if is_production():
        raise RuntimeError(
            f"[FAIL-FAST] {msg}. Production'da uygulama başlatılamaz. "
            'SECRET_KEY üret: python -c "import secrets; print(secrets.token_urlsafe(48))" · '
            "AUTH_ENABLED=true olmalı (kimliksiz erişim yasak)."
        )
    logger.warning("[security] %s (environment=development — uyarı, çalışmaya devam)", msg)
