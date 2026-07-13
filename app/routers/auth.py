"""
M11 (ADR-033) — Auth + Multi-user + KVKK endpoint'leri.

/api/auth: register, login, refresh, logout, me, password-reset, oauth(scaffold)
/api/users/me: KVKK silme (cascade) + veri export (taşınabilirlik)

Basit in-memory rate limiter (W3-041) brute-force koruması için login/register/reset'te.
OAuth (Google/GitHub) ve SMTP şifre-sıfırlama API key gerektirir → API_KEY_TALEP,
scaffold + placeholder. Apple OAuth ücretli program → PLACEHOLDER.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

import jwt as _jwt
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app import auth as _auth
from app.dependencies import get_db, get_current_user
from app.models import User, RevokedToken
from app.services.email import send_password_reset_email, smtp_configured
from app.services import oauth as _oauth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])

KVKK_CONSENT_VERSION = "v1"

# --- Basit in-memory rate limiter (W3-041): per-IP sliding window ---
_RATE: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request, bucket: str) -> None:
    # Env'i call-time'da oku (test/runtime yapılandırması modül import sırasına bağlı olmasın)
    rate_max = int(os.getenv("AUTH_RATE_MAX", "10"))       # pencere başına istek
    rate_window = int(os.getenv("AUTH_RATE_WINDOW", "60"))  # saniye
    ip = request.client.host if request.client else "unknown"
    key = f"{bucket}:{ip}"
    now = time.monotonic()
    q = _RATE[key]
    while q and now - q[0] > rate_window:
        q.popleft()
    if len(q) >= rate_max:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla deneme. Bir dakika sonra tekrar deneyin.",
        )
    q.append(now)


# --- Şemalar ---

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt 72-byte sınırı
    name: Optional[str] = Field(default=None, max_length=100)
    kvkk_consent: bool = Field(description="KVKK açık rıza — zorunlu")


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class AccessOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: Optional[str]
    name: Optional[str]
    oauth_provider: Optional[str]
    kvkk_consent_at: Optional[datetime]
    is_active: bool

    model_config = {"from_attributes": True}


class PasswordResetRequestIn(BaseModel):
    email: EmailStr


class PasswordResetConfirmIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)


# --- Endpoint'ler ---

@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    _rate_limit(request, "register")
    if not body.kvkk_consent:
        raise HTTPException(422, "KVKK açık rıza zorunlu (kvkk_consent=true).")
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Bu e-posta zaten kayıtlı.")
    user = User(
        email=email,
        password_hash=_auth.hash_password(body.password),
        name=body.name or email.split("@")[0],  # name NOT NULL → e-posta local-part default
        kvkk_consent_at=datetime.now(timezone.utc).replace(tzinfo=None),
        kvkk_consent_version=KVKK_CONSENT_VERSION,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(user.id)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    _rate_limit(request, "login")
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    # Zamanlama-güvenli: kullanıcı yoksa da verify çağır (user enumeration önle)
    ok = _auth.verify_password(body.password, user.password_hash if user else None)
    if not user or not ok or not user.is_active:
        raise HTTPException(401, "E-posta veya şifre hatalı.")
    return _issue_tokens(user.id)


@router.post("/refresh", response_model=AccessOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)) -> AccessOut:
    try:
        payload = _auth.decode_token(body.refresh_token, expected_type="refresh")
    except _jwt.PyJWTError:
        raise HTTPException(401, "Geçersiz veya süresi geçmiş refresh token.")
    if db.query(RevokedToken).filter(RevokedToken.jti == payload["jti"]).first():
        raise HTTPException(401, "Refresh token geçersiz kılınmış (logout).")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "Kullanıcı bulunamadı veya pasif.")
    return AccessOut(access_token=_auth.create_access_token(user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = _auth.decode_token(body.refresh_token, expected_type="refresh")
    except _jwt.PyJWTError:
        return None  # zaten geçersiz — idempotent
    if not db.query(RevokedToken).filter(RevokedToken.jti == payload["jti"]).first():
        exp = payload.get("exp")
        db.add(RevokedToken(
            jti=payload["jti"],
            revoked_at=datetime.now(timezone.utc).replace(tzinfo=None),
            expires_at=datetime.fromtimestamp(exp, timezone.utc).replace(tzinfo=None) if exp else None,
        ))
        db.commit()
    return None


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


# --- Şifre sıfırlama (SMTP — API_KEY_TALEP: Brevo/Sendgrid) ---

@router.post("/password-reset-request")
def password_reset_request(
    body: PasswordResetRequestIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    _rate_limit(request, "pwreset")
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    # Kullanıcı enumeration önle: her durumda aynı cevap
    generic = {"message": "E-posta kayıtlıysa sıfırlama bağlantısı gönderildi."}
    if not user or not user.password_hash:
        return generic
    token = _auth.create_password_reset_token(user.id)
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    reset_link = f"{frontend}/auth/reset?token={token}"
    # SMTP yapılandırılmışsa GERÇEK gönderim (BackgroundTasks — istek bloklanmaz).
    if smtp_configured():
        background_tasks.add_task(send_password_reset_email, email, reset_link)
        return generic
    # SMTP yoksa dev modda token döner (yalnız non-prod kolaylığı).
    return {**generic, "_dev_token": token, "_note": "SMTP tanımsız — dev token (prod'da gösterilmez)."}


@router.post("/password-reset-confirm")
def password_reset_confirm(body: PasswordResetConfirmIn, db: Session = Depends(get_db)) -> dict:
    try:
        payload = _auth.decode_token(body.token, expected_type="pwreset")
    except _jwt.PyJWTError:
        raise HTTPException(400, "Geçersiz veya süresi geçmiş sıfırlama token'ı.")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    user.password_hash = _auth.hash_password(body.new_password)
    db.commit()
    return {"message": "Şifre güncellendi."}


# --- OAuth (Google + GitHub — gerçek akış, ADR-033) ---

@router.get("/oauth/{provider}/login")
def oauth_login(provider: str):
    """Kullanıcıyı sağlayıcı (Google/GitHub) onay ekranına yönlendirir (307)."""
    provider = provider.lower()
    if provider not in _oauth.SUPPORTED:
        raise HTTPException(404, f"Desteklenen sağlayıcılar: {_oauth.SUPPORTED}")
    if not _oauth.provider_configured(provider):
        raise HTTPException(
            501,
            f"{provider} OAuth yapılandırılmamış (OAUTH_{provider.upper()}_CLIENT_ID/SECRET gerekli). "
            f"docs/api-key-talep-wave3.md'ye bakın.",
        )
    state = _oauth.new_state()
    return RedirectResponse(_oauth.get_auth_url(provider, state), status_code=307)


@router.get("/callback/{provider}")
def oauth_callback(
    provider: str,
    code: str = "",
    state: str = "",
    db: Session = Depends(get_db),
):
    """Sağlayıcı callback'i: code→token→userinfo, user create/login, JWT + frontend redirect."""
    provider = provider.lower()
    if provider not in _oauth.SUPPORTED:
        raise HTTPException(404, "Bilinmeyen sağlayıcı.")
    if not code or not state:
        raise HTTPException(400, "code veya state eksik.")
    if not _oauth.consume_state(state):
        raise HTTPException(400, "Geçersiz veya süresi geçmiş state (CSRF koruması).")
    try:
        info = _oauth.exchange_code(provider, code)
    except Exception as e:  # noqa: BLE001 — dış OAuth hatası → 400
        logger.warning("[oauth] %s code exchange başarısız: %s", provider, e)
        raise HTTPException(400, f"OAuth doğrulama başarısız: {e}")

    email = info["email"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = db.query(User).filter(User.email == email).first()
    if user:
        if not user.is_active:
            raise HTTPException(403, "Hesap pasif.")
        # İlk OAuth girişinde mevcut hesaba sağlayıcıyı bağla
        if not user.oauth_provider:
            user.oauth_provider = info["provider"]
            user.oauth_sub = info["sub"]
            db.commit()
    else:
        # Yeni OAuth kullanıcısı (şifresiz). KVKK: OAuth onayıyla açık rıza kaydı.
        user = User(
            email=email,
            name=info.get("name") or email.split("@")[0],
            oauth_provider=info["provider"],
            oauth_sub=info["sub"],
            password_hash=None,
            kvkk_consent_at=now,
            kvkk_consent_version=KVKK_CONSENT_VERSION,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    logger.info("[oauth] login success provider=%s user_id=%s email=%s", provider, user.id, email)
    tokens = _issue_tokens(user.id)
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    dest = (f"{frontend}/auth/oauth-success"
            f"?access_token={tokens.access_token}&refresh_token={tokens.refresh_token}")
    return RedirectResponse(dest, status_code=307)


# --- KVKK (silme + export) ---

@users_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """KVKK m.7 silme hakkı: kullanıcı + tüm verisi (cascade). Geri alınamaz."""
    db.delete(user)  # User ilişkileri cascade="all, delete-orphan" → tüm veri silinir
    db.commit()
    return None


@users_router.get("/me/export")
def export_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """KVKK taşınabilirlik: kullanıcının tüm verisi JSON (makine-okur)."""
    from app.serializers import export_user_data  # geç import (döngü önle)
    return export_user_data(user, db)


# --- Yardımcılar ---

def _issue_tokens(user_id: int) -> TokenOut:
    access = _auth.create_access_token(user_id)
    refresh_token, _, _ = _auth.create_refresh_token(user_id)
    return TokenOut(access_token=access, refresh_token=refresh_token)


