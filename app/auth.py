"""
M11 (ADR-033) — Auth çekirdeği: bcrypt şifre hash + PyJWT access/refresh token.

Veri egemenliği: external auth (Firebase/Supabase) YOK — token'lar kendi SECRET_KEY'imizle
imzalanır, kullanıcı verisi kendi DB'sinde kalır (KVKK-dostu).

Token modeli: kısa-ömürlü access (30 dk, Authorization: Bearer) + uzun-ömürlü refresh
(30 gün). Logout = refresh jti'sini RevokedToken'a yaz. bcrypt 72-byte sınırı: register
şeması password'ü max 72'ye kısıtlar.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt

_ALGO = "HS256"
ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "30"))
REFRESH_TTL_DAYS = int(os.getenv("REFRESH_TTL_DAYS", "30"))
BCRYPT_MAX_BYTES = 72  # bcrypt donanımsal sınırı


def auth_enabled() -> bool:
    """AUTH_ENABLED=1 → JWT zorunlu. Aksi (default) tek-kullanıcı fallback (geriye uyum)."""
    return os.getenv("AUTH_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _secret() -> str:
    key = os.getenv("SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "SECRET_KEY tanımsız — auth için .env'de SECRET_KEY gerekli "
            "(python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
        )
    return key


# --- Şifre hash ---

def hash_password(password: str) -> str:
    pw = password.encode("utf-8")
    if len(pw) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Şifre en fazla {BCRYPT_MAX_BYTES} bayt olabilir.")
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT ---

def _create_token(sub: int, token_type: str, ttl: timedelta) -> Tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    exp = now + ttl
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(sub),
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO), jti, exp


def create_access_token(user_id: int) -> str:
    token, _, _ = _create_token(user_id, "access", timedelta(minutes=ACCESS_TTL_MIN))
    return token


def create_refresh_token(user_id: int) -> Tuple[str, str, datetime]:
    """(token, jti, expires_at) — jti/expires RevokedToken temizliği + blacklist için."""
    return _create_token(user_id, "refresh", timedelta(days=REFRESH_TTL_DAYS))


def decode_token(token: str, expected_type: Optional[str] = None) -> dict:
    """Süre/imza doğrular; expected_type verilirse token tipini de. jwt exception'ları fırlatır."""
    payload = jwt.decode(token, _secret(), algorithms=[_ALGO])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"beklenen token tipi '{expected_type}', gelen '{payload.get('type')}'"
        )
    return payload


# --- Şifre sıfırlama token'ı (SMTP akışı, API_KEY_TALEP: Brevo/Sendgrid) ---

def create_password_reset_token(user_id: int, ttl_minutes: int = 30) -> str:
    token, _, _ = _create_token(user_id, "pwreset", timedelta(minutes=ttl_minutes))
    return token
