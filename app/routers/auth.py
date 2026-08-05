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
from app.services.email import (  # BUG #215: e-posta düzeltme akışı
    _mask,
    send_email_change_verification,
    send_email_changed_notice,
    send_password_reset_email,
    smtp_configured,
)
from app.services import oauth as _oauth
from app.settings import is_production  # BUG #185: prod'da PKCE çerezi yalnız HTTPS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])

# P4: v2 — v1 metni uygulamayi yalniz self-host varsayiyordu ("veriniz kendi sunucunuzda");
# barindirilan kapali betada bu YANLIS beyandi. v2 dogru veri-sorumlusu tanimini icerir.
KVKK_CONSENT_VERSION = "v2"

# M21: rate limiter app/rate_limit.py'a taşındı (per-bucket production değerleri).
# _rate_limit/_RATE alias'ları test uyumu için korunur (auth_mod._RATE.clear()).
from app.rate_limit import rate_limit as _rate_limit, _RATE  # noqa: E402,F401


# --- Şemalar ---

class RegisterIn(BaseModel):
    # BUG #199 (P7): kapali betada davet kodu ZORUNLU (production varsayilani).
    invite_code: Optional[str] = Field(default=None, max_length=64)
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


class PasswordChangeIn(BaseModel):
    """BUG #190 (P3): giris yapmis kullanicinin sifre degistirmesi."""
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class PasswordResetConfirmIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)


class EmailChangeIn(BaseModel):
    """P4.4 (BUG #215): KVKK 'duzeltme hakki' — e-posta adresini duzeltme talebi."""
    new_email: EmailStr
    # OAuth-only hesapta sifre YOKTUR; orada yeni adrese giden dogrulama tek kanittir.
    current_password: Optional[str] = Field(default=None, max_length=72)


class EmailChangeConfirmIn(BaseModel):
    token: str


def _sifre_dogrula(password: str) -> None:
    """BUG #187: politika ihlalinde 422 (kayit + sifirlama ayni kurala tabi)."""
    sorunlar = _auth.password_problems(password)
    if sorunlar:
        raise HTTPException(422, "Sifre kabul edilmedi: " + "; ".join(sorunlar))


# --- Endpoint'ler ---

# BUG #202: kayit yaniti — var olan/olmayan e-posta AYIRT EDILEMEZ olmali.
_KAYIT_JENERIK_YANIT = {"message": "Kayıt alındı. E-postandaki bağlantıyla hesabını etkinleştir."}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    _rate_limit(request, "register", db=db)  # BUG #182: paylasilan sayac
    if not body.kvkk_consent:
        raise HTTPException(422, "KVKK açık rıza zorunlu (kvkk_consent=true).")
    _sifre_dogrula(body.password)  # BUG #187: yaygin/zayif sifre reddi
    email = body.email.lower().strip()

    # BUG #199 (P7): KAPALI BETA. Kayit ucu herkese acikti -> domain canliya cikar cikmaz
    # baglantiyi bilen herkes hesap acabilirdi. Production varsayilani invite_only
    # (fail-closed): acik kayit ancak operator ACIKCA REGISTRATION_MODE=open yazarsa.
    from app.beta_access import invite_required, davet_dogrula, davet_kullan
    davet = None
    if invite_required():
        davet = davet_dogrula(db, body.invite_code, email)
        if davet is None:
            # Sebep AYRISTIRILMAZ (kod deneme saldirisina bilgi verilmez).
            raise HTTPException(403, "Kayıt şu anda davetlilere açık. Geçerli bir davet kodu gerekli.")
    # BUG #202 (P8): 409 "bu e-posta zaten kayitli" yaniti KULLANICI LISTESI SIZDIRIR
    # (enumerasyon). Dogrulama modunda kayit HER DURUMDA ayni yaniti dondurur; hesap
    # ancak e-postadaki baglanti ile etkinlesir. Davetli-only modda bu gerekmez
    # (kayit zaten operator kontrolunde) -> eski davranis korunur.
    from app.beta_access import email_verification_required
    dogrulama_gerekli = email_verification_required()
    mevcut = db.query(User).filter(User.email == email).first()
    if mevcut is not None:
        if not dogrulama_gerekli:
            raise HTTPException(409, "Bu e-posta zaten kayıtlı.")
        # Sessiz cikis: saldirgan "kayitli mi degil mi" AYIRT EDEMEZ.
        logger.info("[auth] var olan e-postaya kayit denemesi (yanit jenerik)")
        return _KAYIT_JENERIK_YANIT
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
    if dogrulama_gerekli:
        user.is_active = False          # BUG #202: dogrulanana kadar giris YOK
    ensure_personal_workspace(db, user, commit=False)
    if davet is not None:
        davet_kullan(db, davet, user.id)   # BUG #199: davet TEK KULLANIMLIK, ayni transaction
    db.commit()
    db.refresh(user)

    if dogrulama_gerekli:
        # Token VERILMEZ: hesap dogrulanana kadar acilmaz. E-posta gonderilemezse bile
        # yanit AYNI kalir (enumerasyon kapali); operator log'dan gorur.
        dogrulama = _auth.create_email_verification_token(user.id)
        link = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')}/auth/verify?token={dogrulama}"
        try:
            from app.services.email import send_email, smtp_configured
            if smtp_configured():
                send_email(email, "FinancialOS — e-posta doğrulama",
                           f"Hesabını etkinleştirmek için: {link}",
                           f'<p>Hesabını etkinleştirmek için <a href="{link}">buraya tıkla</a>.</p>')
            else:
                logger.warning("[auth] SMTP yok — doğrulama bağlantısı gönderilemedi (user=%s)", user.id)
        except Exception:
            logger.exception("[auth] doğrulama e-postası gönderilemedi (user=%s)", user.id)
        return _KAYIT_JENERIK_YANIT

    return _issue_tokens(user)


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)) -> dict:
    """BUG #202: e-posta doğrulama bağlantısı — hesabı etkinleştirir (tek kullanımlık)."""
    try:
        payload = _auth.decode_token(token, expected_type="email_verify")
    except _jwt.PyJWTError:
        raise HTTPException(400, "Geçersiz veya süresi geçmiş doğrulama bağlantısı.")
    if _auth.token_revoked(db, payload.get("jti")):
        raise HTTPException(400, "Bu bağlantı daha önce kullanıldı.")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    user.email_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user.is_active = True
    _auth.revoke_jti(db, payload.get("jti"), payload.get("exp"), commit=False)
    db.commit()
    return {"message": "E-posta doğrulandı. Artık giriş yapabilirsin."}


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


@router.post("/change-password", response_model=TokenOut)
def change_password(
    body: PasswordChangeIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenOut:
    """BUG #190 (P3): giris yapmis kullanici sifresini degistirir.

    Onceden TEK yol e-posta ile sifirlamaydi; SMTP yapilandirilmamis bir kurulumda
    (yeni deploy) kullanici sifresini HIC degistiremiyordu. Mevcut sifre dogrulanir,
    politika uygulanir (BUG #187), diger TUM oturumlar dusurulur (BUG #172 ailesi) ve
    cagirana yeni token cifti verilir (kullanici kendi islemiyle atilmaz).
    """
    _rate_limit(request, "login", db=db)  # brute-force: mevcut sifre denemesi
    if not user.password_hash:
        raise HTTPException(400, "Bu hesap sosyal giris (OAuth) ile acilmis — sifresi yok.")
    if not _auth.verify_password(body.current_password, user.password_hash):
        raise HTTPException(401, "Mevcut sifre hatali.")
    _sifre_dogrula(body.new_password)
    user.password_hash = _auth.hash_password(body.new_password)
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1  # diger oturumlar duser
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


# --- E-posta değiştirme (P4.4 / BUG #215 — KVKK "düzeltme hakkı") ---

@router.post("/change-email")
def change_email(
    body: EmailChangeIn,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """E-posta DEĞİŞTİRME talebi — yeni adrese doğrulama gönderilir, adres HEMEN değişmez.

    BUG #215 (P4.4): e-posta hiçbir yerden değiştirilemiyordu. İki sonucu vardı:
    (a) `docs/legal/kvkk-consent-v2.md` "verilerinizi dilediğiniz an güncelleyebilirsiniz"
        diyor — e-posta için bu YANLIŞ BEYANDI (KVKK 11/d düzeltme hakkı fiilen yok).
    (b) Kayıtta adresini yanlış yazan kullanıcı KALICI olarak kilitleniyordu: doğrulama
        postası gelmez, şifre sıfırlanamaz, kimse ona ulaşamaz, kendisi de düzeltemez.
        Açık betada bu, sessizce kaybedilen kullanıcı demektir.

    Güvenlik tasarımı:
    - Şifresi olan hesapta MEVCUT ŞİFRE zorunlu (çalınmış oturumla adres kaçırılamaz).
    - Adres ancak YENİ adrese giden bağlantı tıklanınca değişir (yanlış yazım hesabı öldürmez).
    - Yanıt her durumda AYNIDIR: adresin kayıtlı olup olmadığı sızmaz (BUG #202 dersi).
    """
    _rate_limit(request, "pwreset", db=db)   # BUG #182: paylaşılan sayaç (posta gönderen uç)
    yeni = body.new_email.lower().strip()
    mevcut = (user.email or "").lower().strip()

    if user.password_hash:
        if not body.current_password:
            raise HTTPException(422, "Mevcut sifre gerekli.")
        if not _auth.verify_password(body.current_password, user.password_hash):
            raise HTTPException(401, "Mevcut sifre hatali.")

    generic = {"message": "Adres uygunsa doğrulama bağlantısı yeni adrese gönderildi."}
    if yeni == mevcut:
        # Enumerasyon riski yok: kullanıcı zaten kendi adresini biliyor.
        raise HTTPException(400, "Yeni adres mevcut adresle ayni.")
    # Adres başkasındaysa SESSİZ kalınır — "bu e-posta kayıtlı" demek kullanıcı listesi sızdırır.
    if db.query(User).filter(User.email == yeni).first():
        logger.info("[auth] e-posta degistirme: hedef adres zaten kayitli (sessiz gecildi)")
        return generic

    token = _auth.create_email_change_token(user.id, yeni, mevcut)
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    link = f"{frontend}/auth/change-email?token={token}"
    if smtp_configured():
        background_tasks.add_task(send_email_change_verification, yeni, link)
        return generic
    from app.settings import is_production
    if is_production():
        # BUG #170 dersi: production'da token ASLA yanıtta dönmez (tam hesap ele geçirme).
        logger.error("[auth] SMTP yok — e-posta degistirme dogrulamasi GONDERILEMEDI.")
        return generic
    return {**generic, "_dev_token": token, "_note": "SMTP tanımsız — dev token (prod'da gösterilmez)."}


@router.post("/change-email-confirm")
def change_email_confirm(
    body: EmailChangeConfirmIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Yeni adrese giden bağlantı — adres BURADA değişir (BUG #215)."""
    try:
        payload = _auth.decode_token(body.token, expected_type="email_change")
    except _jwt.PyJWTError:
        raise HTTPException(400, "Geçersiz veya süresi geçmiş doğrulama bağlantısı.")
    if _auth.token_revoked(db, payload.get("jti")):
        raise HTTPException(400, "Bu bağlantı daha önce kullanıldı.")

    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if not user.is_active:
        raise HTTPException(403, "Hesap pasif.")

    # Talep anındaki adres hâlâ geçerli mi? Arada adres değiştiyse eski bağlantı ÖLÜR —
    # aksi halde eski bir bağlantı tekrar oynatılıp hesap önceki adrese döndürülebilirdi.
    if (user.email or "").lower().strip() != (payload.get("old") or ""):
        raise HTTPException(400, "Bağlantı artık geçerli değil (adres bu arada değişti).")

    yeni = (payload.get("new") or "").lower().strip()
    if not yeni:
        raise HTTPException(400, "Bağlantı eksik.")
    # Yarış: talep ile onay arasında başkası aynı adresi almış olabilir.
    if db.query(User).filter(User.email == yeni, User.id != user.id).first():
        raise HTTPException(409, "Bu adres artık kullanilamiyor.")

    eski = user.email
    user.email = yeni
    user.email_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)  # yeni adres kanıtlandı
    # Kimlik değişti: tüm oturumlar düşer (şifre sıfırlamayla aynı çizgi, BUG #172).
    user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
    _auth.revoke_jti(db, payload.get("jti"), payload.get("exp"), commit=False)
    db.commit()

    # ESKİ adrese bildirim: çalınmış oturumla yapılan değişiklik görünür olsun.
    if eski and smtp_configured():
        background_tasks.add_task(send_email_changed_notice, eski, _mask(yeni))
    return {"message": "E-posta adresin güncellendi. Güvenlik için tüm oturumlar kapatıldı."}


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
    # BUG #204 (P3.4/H6): ORM cascade'ine guvenmek YETMEDI — 6 tablonun cascade iliskisi
    # yoktu ve silme SIRASI kosullara gore degisiyordu (verisi olan kullanici hesabini
    # SILEMIYORDU). Artik sira SEMADAN turetilir (deterministik).
    from app.kvkk import purge_user_data
    # Cocuk satirlar Core-DELETE ile (deterministik sira), kullanici satiri ORM ile:
    # boylece session tutarli kalir (yetim nesne -> ObjectDeleted/DetachedInstanceError).
    purge_user_data(db, user.id, delete_user_row=False)
    db.delete(user)
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


