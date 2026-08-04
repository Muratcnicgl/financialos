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
from app.settings import is_production  # BUG #185: prod'da PKCE çerezi yalnız HTTPS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])

KVKK_CONSENT_VERSION = "v1"

# M21: rate limiter app/rate_limit.py'a taşındı (per-bucket production değerleri).
# _rate_limit/_RATE alias'ları test uyumu için korunur (auth_mod._RATE.clear()).
from app.rate_limit import rate_limit as _rate_limit, _RATE  # noqa: E402,F401


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


def _sifre_dogrula(password: str) -> None:
    """BUG #187: politika ihlalinde 422 (kayit + sifirlama ayni kurala tabi)."""
    sorunlar = _auth.password_problems(password)
    if sorunlar:
        raise HTTPException(422, "Sifre kabul edilmedi: " + "; ".join(sorunlar))


# --- Endpoint'ler ---

@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    _rate_limit(request, "register", db=db)  # BUG #182: paylasilan sayac
    if not body.kvkk_consent:
        raise HTTPException(422, "KVKK açık rıza zorunlu (kvkk_consent=true).")
    _sifre_dogrula(body.password)  # BUG #187: yaygin/zayif sifre reddi
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
    db.flush()  # user.id gerekli
    # M62 (ADR-037): personal workspace + owner membership AYNI transaction'da
    from app.services.workspace_setup import ensure_personal_workspace
    ensure_personal_workspace(db, user, commit=False)
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    _rate_limit(request, "login", db=db)  # BUG #182: paylasilan sayac
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    # Zamanlama-güvenli: kullanıcı yoksa da verify çağır (user enumeration önle)
    ok = _auth.verify_password(body.password, user.password_hash if user else None)
    if not user or not ok or not user.is_active:
        raise HTTPException(401, "E-posta veya şifre hatalı.")
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)) -> TokenOut:
    """Access token yeniler ve refresh token'i ROTE EDER (BUG #186).

    Eskiden eski refresh iptal edilmiyor, yenisi uretilmiyordu: calinmis bir token 30 gun
    boyunca sinirsiz kullanilabiliyor ve sizinti asla tespit edilemiyordu. Artik her
    kullanimda eski jti kara listeye yazilir, yeni refresh donulur. Kara listedeki bir
    refresh yeniden kullanilirsa bu bir SIZINTI sinyalidir -> kullanicinin TUM oturumlari
    dusurulur (OAuth 2.1 / RFC 9700 refresh-token reuse detection).
    """
    try:
        payload = _auth.decode_token(body.refresh_token, expected_type="refresh")
    except _jwt.PyJWTError:
        raise HTTPException(401, "Geçersiz veya süresi geçmiş refresh token.")
    user = db.get(User, int(payload["sub"]))
    if db.query(RevokedToken).filter(RevokedToken.jti == payload["jti"]).first():
        # BUG #186: iptal edilmis refresh YENIDEN kullanildi -> sizinti varsay, hepsini dusur
        if user is not None:
            user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
            db.commit()
            logger.warning("[auth] refresh token tekrar-kullanimi tespit edildi user_id=%s "
                           "— tum oturumlar dusuruldu", user.id)
        raise HTTPException(401, "Refresh token geçersiz kılınmış. Yeniden giriş yapın.")
    if not user or not user.is_active:
        raise HTTPException(401, "Kullanıcı bulunamadı veya pasif.")
    # BUG #172 (P2): şifre sıfırlandıysa, ondan ÖNCE üretilmiş refresh token ölür.
    if not _auth.token_version_ok(payload, user):
        raise HTTPException(401, "Refresh token geçersiz (şifre değişti — yeniden giriş yapın).")
    _auth.revoke_jti(db, payload.get("jti"), payload.get("exp"), commit=True)  # rotasyon
    return _issue_tokens(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    # BUG #172 (P2/c): logout YALNIZ refresh'i iptal ediyordu; eldeki access token 30 dakika
    # daha çalışıyordu (ortak bilgisayarda "çıkış yaptım" yanılsaması). Authorization
    # başlığındaki access token da kara listeye alınır.
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        try:
            acc = _auth.decode_token(header[7:].strip(), expected_type="access")
            _auth.revoke_jti(db, acc.get("jti"), acc.get("exp"), commit=False)
        except _jwt.PyJWTError:
            pass  # bozuk/expired access → zaten geçersiz

    try:
        payload = _auth.decode_token(body.refresh_token, expected_type="refresh")
    except _jwt.PyJWTError:
        db.commit()  # access iptali yazıldıysa kaydet
        return None  # refresh zaten geçersiz — idempotent
    _auth.revoke_jti(db, payload.get("jti"), payload.get("exp"), commit=False)
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
    _rate_limit(request, "pwreset", db=db)  # BUG #182: paylasilan sayac
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
    # BUG #170 fix (P2): koşul YALNIZ smtp_configured() idi — production'da SMTP eksik/bozuksa
    # geçerli sıfırlama token'ı HTTP yanıtında düz metin dönüyordu. Herhangi biri, herhangi bir
    # e-posta için token alıp şifreyi değiştirebilirdi (tam hesap ele geçirme) + token'ın dönüp
    # dönmemesi kullanıcı-enumerasyonu sızdırıyordu. Production'da ASLA token dönmez.
    from app.settings import is_production
    if is_production():
        logger.error(
            "[auth] SMTP yapılandırılmamış — şifre sıfırlama e-postası GÖNDERİLEMEDİ. "
            "Kullanıcı sıfırlama yapamaz; SMTP_* değişkenlerini ayarla."
        )
        return generic
    # SMTP yoksa dev modda token döner (yalnız non-prod kolaylığı).
    return {**generic, "_dev_token": token, "_note": "SMTP tanımsız — dev token (prod'da gösterilmez)."}


@router.post("/password-reset-confirm")
def password_reset_confirm(body: PasswordResetConfirmIn, db: Session = Depends(get_db)) -> dict:
    try:
        payload = _auth.decode_token(body.token, expected_type="pwreset")
    except _jwt.PyJWTError:
        raise HTTPException(400, "Geçersiz veya süresi geçmiş sıfırlama token'ı.")
    # BUG #172 (P2/b): sıfırlama token'ı TEK KULLANIMLIK değildi — posta kutusuna/geçmişe
    # erişen biri aynı token'la kurban şifresini tekrar değiştirip hesabı geri alabiliyordu.
    if _auth.token_revoked(db, payload.get("jti")):
        raise HTTPException(400, "Bu sıfırlama bağlantısı daha önce kullanıldı.")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if not user.is_active:
        raise HTTPException(403, "Hesap pasif.")
    _sifre_dogrula(body.new_password)  # BUG #187: sifirlamada da ayni politika
    user.password_hash = _auth.hash_password(body.new_password)
    # BUG #172 (P2/a): mevcut TÜM oturumları düşür — çalınmış refresh/access token'lar ölür.
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    _auth.revoke_jti(db, payload.get("jti"), payload.get("exp"), commit=False)
    db.commit()
    return {"message": "Şifre güncellendi. Güvenlik için tüm oturumlar kapatıldı."}


# --- OAuth (Google + GitHub — gerçek akış, ADR-033) ---

@router.get("/oauth/{provider}/login")
def oauth_login(provider: str, request: Request, db: Session = Depends(get_db)):
    """Kullanıcıyı sağlayıcı (Google/GitHub) onay ekranına yönlendirir (307)."""
    _rate_limit(request, "oauth", db=db)  # BUG #182: paylasilan sayac  # M21: 10/dk
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
    # BUG #185 (b): PKCE verifier httpOnly çerezde taşınır — state içinde DEĞİL, çünkü
    # state tarayıcı ve sağlayıcı üzerinden geçer; verifier orada açık olsaydı PKCE'nin
    # koruması ortadan kalkardı. Çerez multi-worker'da da çalışır (istemci taşır).
    verifier = _oauth.new_code_verifier()
    resp = RedirectResponse(_oauth.get_auth_url(provider, state, code_verifier=verifier),
                            status_code=307)
    resp.set_cookie(
        "fos_pkce", verifier,
        max_age=600, httponly=True, samesite="lax",
        secure=is_production(),  # dev'de http, prod'da yalnız HTTPS
        path="/api/auth",
    )
    return resp


@router.get("/callback/{provider}")
def oauth_callback(
    provider: str,
    request: Request,
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
    # BUG #185 (a): state artik STATELESS imzali token; tuketim DB uzerinden kalici
    # (cok-worker'da /login ve /callback farkli worker'lara dusebilir).
    if not _oauth.consume_state(state, db):
        raise HTTPException(400, "Geçersiz veya süresi geçmiş state (CSRF koruması).")
    verifier = request.cookies.get("fos_pkce")  # BUG #185 (b): PKCE
    try:
        info = _oauth.exchange_code(provider, code, code_verifier=verifier)
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

    # M62 (ADR-037): her user'ın personal workspace'i olsun (yeni VEYA mevcut, idempotent)
    from app.services.workspace_setup import ensure_personal_workspace
    ensure_personal_workspace(db, user, commit=True)

    # BUG #180 (P2): tam e-posta INFO log'una yazılıyordu (KVKK: log dosyası kullanıcı listesi
    # haline geliyordu). user_id yeterli — kimlik zaten DB'de eşlenebilir.
    logger.info("[oauth] login success provider=%s user_id=%s", provider, user.id)
    # BUG #179 (P2): token'lar ARTIK URL'de taşınmaz — tek-kullanımlık 60 sn'lik değişim kodu.
    exchange_code = _auth.create_oauth_exchange_code(user.id)
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    dest = f"{frontend}/auth/oauth-success?code={exchange_code}"
    resp = RedirectResponse(dest, status_code=307)
    resp.delete_cookie("fos_pkce", path="/api/auth")  # BUG #185: verifier tek kullanimlik
    return resp


class OAuthExchangeIn(BaseModel):
    code: str = Field(min_length=10, max_length=4096)


@router.post("/oauth/exchange", response_model=TokenOut)
def oauth_exchange(body: OAuthExchangeIn, request: Request,
                   db: Session = Depends(get_db)) -> TokenOut:
    """BUG #179: değişim kodunu token'la takas eder (tek kullanımlık, 60 sn)."""
    _rate_limit(request, "login", db=db)  # BUG #182: paylasilan sayac
    try:
        payload = _auth.decode_token(body.code, expected_type="oauth_exchange")
    except _jwt.PyJWTError:
        raise HTTPException(401, "Geçersiz veya süresi geçmiş oturum kodu.")
    if _auth.token_revoked(db, payload.get("jti")):
        raise HTTPException(401, "Bu oturum kodu daha önce kullanıldı.")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "Kullanıcı bulunamadı veya pasif.")
    _auth.revoke_jti(db, payload.get("jti"), payload.get("exp"), commit=True)
    return _issue_tokens(user)


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

def _issue_tokens(user: User) -> TokenOut:
    """BUG #172: token'lar kullanıcının güncel `token_version`'ını (tv) taşır."""
    tv = int(getattr(user, "token_version", 0) or 0)
    access = _auth.create_access_token(user.id, tv)
    refresh_token, _, _ = _auth.create_refresh_token(user.id, tv)
    return TokenOut(access_token=access, refresh_token=refresh_token)


