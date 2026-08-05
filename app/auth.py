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


# --- Sifre politikasi (BUG #187, P2) ---

# En yaygin sizdirilmis sifrelerin cekirdegi + TR'ye ozgu yaygin secimler. Tam bir
# breach-listesi (HIBP) cevrimici sorgu gerektirir; kapali beta icin yerel liste +
# desen kontrolu (tekrarli/ardisik karakter) yeterli, dis servise veri gitmez.
_YAYGIN_SIFRELER = {
    "12345678", "123456789", "1234567890", "password", "password1", "password123",
    "qwerty123", "qwertyui", "11111111", "00000000", "abc12345", "iloveyou",
    "admin123", "welcome1", "letmein1", "sunshine", "princess", "football",
    "parola123", "sifre123", "parola12", "turkiye1", "galatasaray", "fenerbahce",
    "besiktas", "trabzonspor", "ankara123", "istanbul", "deneme123", "asdasd123",
}


def password_problems(password: str) -> list[str]:
    """BUG #187 (P2): sifre politikasi YALNIZ uzunluktu (>=8).

    '12345678' / 'parola123' gibi ilk-1000 listesindeki sifreler kabul ediliyordu; rate
    limit ve cok-worker sorunlariyla birlesince cevrimici brute-force gercekci hale
    geliyordu. Uzunluk + yaygin-liste + basit desen kontrolu.
    """
    p = (password or "").strip()
    sorunlar: list[str] = []
    if len(p) < 8:
        sorunlar.append("en az 8 karakter olmali")
    if p.lower() in _YAYGIN_SIFRELER:
        sorunlar.append("cok yaygin kullanilan bir sifre (tahmin edilmesi kolay)")
    if p and len(set(p)) <= 2:
        sorunlar.append("ayni karakterin tekrari (ornek: 11111111)")
    if p.isdigit():
        sorunlar.append("yalnizca rakamlardan olusamaz")
    return sorunlar


# --- JWT ---

def _create_token(sub: int, token_type: str, ttl: timedelta,
                  token_version: int = 0) -> Tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    exp = now + ttl
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(sub),
        "type": token_type,
        "jti": jti,
        "tv": int(token_version or 0),  # BUG #172: oturum geçersizleme sayacı
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO), jti, exp


def create_access_token(user_id: int, token_version: int = 0) -> str:
    token, _, _ = _create_token(user_id, "access", timedelta(minutes=ACCESS_TTL_MIN),
                                token_version)
    return token


def create_refresh_token(user_id: int, token_version: int = 0) -> Tuple[str, str, datetime]:
    """(token, jti, expires_at) — jti/expires RevokedToken temizliği + blacklist için."""
    return _create_token(user_id, "refresh", timedelta(days=REFRESH_TTL_DAYS), token_version)


def decode_token(token: str, expected_type: Optional[str] = None) -> dict:
    """Süre/imza doğrular; expected_type verilirse token tipini de. jwt exception'ları fırlatır."""
    payload = jwt.decode(token, _secret(), algorithms=[_ALGO])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"beklenen token tipi '{expected_type}', gelen '{payload.get('type')}'"
        )
    return payload


# --- Şifre sıfırlama token'ı (SMTP akışı, API_KEY_TALEP: Brevo/Sendgrid) ---

def create_oauth_exchange_code(user_id: int, ttl_seconds: int = 60) -> str:
    """BUG #179 (P2): OAuth sonrası TEK-KULLANIMLIK, kısa ömürlü değişim kodu.

    Eskiden access + 30 GÜNLÜK refresh token yönlendirme URL'inde taşınıyordu (tarayıcı
    geçmişi, access log, Referer). Artık URL yalnız bu kodu taşır; token'lar
    `POST /api/auth/oauth/exchange` yanıt GÖVDESİNDE döner. Kod stateless JWT'dir →
    çok-worker kurulumda da çalışır; kullanıldığında jti kara listeye yazılır.
    """
    token, _, _ = _create_token(user_id, "oauth_exchange", timedelta(seconds=ttl_seconds))
    return token


def create_email_verification_token(user_id: int, ttl_hours: int = 48) -> str:
    """P8 (BUG #202): e-posta dogrulama baglantisi icin token (48 saat)."""
    token, _, _ = _create_token(user_id, "email_verify", timedelta(hours=ttl_hours))
    return token


def create_password_reset_token(user_id: int, token_version: int = 0,
                                ttl_minutes: int = 30) -> str:
    """BUG #225 (D04): `token_version` artık payload'a GİRER.

    Eskiden `tv` daima 0 idi → sıfırlama bağlantısı, kullanıcı şifresini değiştirdikten
    (sayaç arttıktan) sonra da geçerli kalıyordu: posta kutusuna geçici erişen biri
    bağlantıyı bekletip hesabı kalıcı ele geçirebiliyordu. `password_reset_confirm`
    artık `token_version_ok(...)` ile bu claim'i doğrular; sayacı artıran her olay
    (şifre değişimi, başka bir sıfırlamanın kullanılması) bekleyen bağlantıları öldürür.
    """
    token, _, _ = _create_token(user_id, "pwreset", timedelta(minutes=ttl_minutes),
                                token_version)
    return token


def create_email_change_token(user_id: int, new_email: str, current_email: Optional[str],
                              ttl_hours: int = 2) -> str:
    """P4.4 (BUG #215): e-posta DEĞİŞTİRME token'ı — yeni adrese gönderilir.

    Token iki ek iddia taşır:
    - `new`: onaylanınca yazılacak adres. Adres token'ın İÇİNDE olduğu için sunucuda
      "bekleyen değişiklik" tablosu gerekmez ve çok-worker kurulumda da çalışır (L10).
    - `old`: talep anındaki adres. Onayda hâlâ aynı mı diye bakılır; arada e-posta
      değiştiyse eski bağlantı ölür (tekrar-oynatma ile eski adrese geri döndürme yok).

    Kısa ömür (2 saat) bilinçli: bağlantı, çalınmış bir posta kutusunda uzun süre
    yaşayan bir hesap-ele-geçirme aracına dönüşmemeli.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=ttl_hours)
    payload = {
        "sub": str(user_id),
        "type": "email_change",
        "jti": uuid.uuid4().hex,
        "new": (new_email or "").lower().strip(),
        "old": (current_email or "").lower().strip(),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


# --- BUG #172 (P2): oturum geçersizleme + jti kara listesi ---

def token_revoked(db, jti: Optional[str]) -> bool:
    """jti kara listede mi? (logout / tek-kullanımlık sıfırlama token'ı)"""
    if not jti:
        return False
    from app.models import RevokedToken
    return db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None


def revoke_jti(db, jti: Optional[str], exp: Optional[int] = None, commit: bool = True) -> None:
    """jti'yi kara listeye ekler (idempotent)."""
    if not jti:
        return
    from app.models import RevokedToken
    if db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        return
    db.add(RevokedToken(
        jti=jti,
        revoked_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expires_at=(datetime.fromtimestamp(exp, timezone.utc).replace(tzinfo=None)
                    if exp else None),
    ))
    if commit:
        db.commit()


def token_version_ok(payload: dict, user) -> bool:
    """Token'ın `tv` claim'i kullanıcının güncel `token_version`'ı ile eşleşiyor mu?

    Şifre sıfırlama/değişimi sayacı artırır → o andan önceki TÜM token'lar (çalınmış
    refresh dahil) geçersizleşir. `tv` taşımayan eski token'lar 0 sayılır; sayaç hiç
    artmamış kullanıcılarda (0) geriye-uyum korunur.
    """
    return int(payload.get("tv", 0) or 0) == int(getattr(user, "token_version", 0) or 0)
