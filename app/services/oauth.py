"""
M11 (ADR-033) — OAuth (Google + GitHub) sosyal giriş. scaffold → gerçek akış (14 Tem 2026).

Karar (K10): Authlib `OAuth2Session` (requests-tabanlı, sync — router sync deseniyle uyumlu,
SessionMiddleware gerektirmez). State kendi elimizde (in-memory dict, 10 dk expiry) →
deterministik, ADR-001 ruhu (LLM yok, saf protokol). Token exchange + userinfo Authlib içinde.

Wave-4: state store Redis'e taşınır (çok-instance için). Şimdilik tek-process in-memory yeterli.
"""
from __future__ import annotations

import os
import secrets
import time
from typing import Optional

from authlib.integrations.requests_client import OAuth2Session


def _dis_cagri_timeout() -> float:
    """Sağlayıcıya yapılan HTTP çağrılarının azami süresi (saniye).

    BUG #263 (P5.5, sınıf taraması): burada HİÇBİR timeout yoktu. `requests`/authlib
    timeout verilmediğinde bağlantı işletim sistemi TCP sınırlarına kadar (dakikalarca)
    asılı kalabilir — ve bu sırada isteğin DB oturumu AÇIKTIR. Google/GitHub yavaşlarsa
    her eşzamanlı giriş bir bağlantıyı süresiz tutar; havuz tükenir, uygulama düşer.
    Sınırsız beklemenin kullanıcıya da faydası yok: 15 sn'de dönmeyen bir OAuth akışı
    zaten başarısızdır, "tekrar dene" demek dürüst olandır.
    """
    try:
        return max(1.0, float(os.getenv("OAUTH_TIMEOUT", "15")))
    except (TypeError, ValueError):
        return 15.0

# provider → endpoint + scope + env anahtarları
_PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
        "cid_env": "OAUTH_GOOGLE_CLIENT_ID",
        "secret_env": "OAUTH_GOOGLE_CLIENT_SECRET",
        "pkce": True,   # BUG #185: Google PKCE destekler
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "emails_url": "https://api.github.com/user/emails",
        "scope": "read:user user:email",
        "cid_env": "OAUTH_GITHUB_CLIENT_ID",
        "secret_env": "OAUTH_GITHUB_CLIENT_SECRET",
        "pkce": False,  # GitHub OAuth App'leri PKCE'yi resmî desteklemiyor
    },
}

SUPPORTED = tuple(_PROVIDERS.keys())

# state → oluşturma zamanı (10 dk expiry). CSRF + callback eşleştirme.
_STATE_TTL = 600
_states: dict[str, float] = {}          # (tarihsel; BUG #185 sonrası kullanılmıyor)
_consumed_states: set[str] = set()      # BUG #185: DB'siz yolda tek-kullanım kaydı


def _creds(provider: str):
    p = _PROVIDERS[provider]
    return os.getenv(p["cid_env"], "").strip(), os.getenv(p["secret_env"], "").strip()


def provider_configured(provider: str) -> bool:
    if provider not in _PROVIDERS:
        return False
    cid, secret = _creds(provider)
    return bool(cid and secret)


def redirect_uri(provider: str) -> str:
    """Google/GitHub konsolunda kayıtlı callback (varsayılan localhost:8000)."""
    base = os.getenv("OAUTH_REDIRECT_BASE", "http://localhost:8000").rstrip("/")
    return f"{base}/api/auth/callback/{provider}"


def new_state() -> str:
    """BUG #185 (P2): STATELESS state — imzalı, 10 dk ömürlü, tek kullanımlık token.

    Eskiden process-yerel bir sözlükteydi: gunicorn çok-worker kurulumunda /login
    worker-A'da, callback worker-B'de işlenince "Geçersiz state" hatası veriyordu
    (girişlerin kabaca yarısı) ve her restart akışları düşürüyordu.
    """
    from app import auth as _auth
    from datetime import timedelta
    token, _, _ = _auth._create_token(0, "oauth_state", timedelta(seconds=_STATE_TTL))
    return token


def consume_state(state: str, db=None) -> bool:
    """State geçerli + süresi dolmamışsa True döner ve TEK KULLANIMLIK tüketir.

    db verilirse tüketim RevokedToken üzerinden kalıcıdır (tüm worker'lar görür).
    Verilmezse (dev/test) yalnız imza+süre doğrulanır.
    """
    from app import auth as _auth
    import jwt as _jwt
    try:
        payload = _auth.decode_token(state, expected_type="oauth_state")
    except _jwt.PyJWTError:
        return False
    jti = payload.get("jti")
    if db is None:
        # DB yoksa (dev/test) tek-kullanım garantisi process-içi tutulur — güvenlik
        # sözleşmesi hiçbir çağrı yolunda gevşemez, yalnız kalıcılığı azalır.
        if jti in _consumed_states:
            return False
        _consumed_states.add(jti)
        return True
    if _auth.token_revoked(db, jti):
        return False  # tekrar kullanım (replay)
    _auth.revoke_jti(db, jti, payload.get("exp"), commit=True)
    return True


# --- PKCE (BUG #185 b) ---

def new_code_verifier() -> str:
    """RFC 7636 code_verifier (43-128 karakter, URL-safe)."""
    return secrets.token_urlsafe(64)


def _code_challenge(verifier: str) -> str:
    import base64
    import hashlib
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _prune_states() -> None:
    now = time.time()
    for s in [s for s, ts in _states.items() if now - ts > _STATE_TTL]:
        _states.pop(s, None)


def get_auth_url(provider: str, state: str, code_verifier: Optional[str] = None) -> str:
    """Kullanıcının yönlendirileceği sağlayıcı yetkilendirme URL'i.

    BUG #185 (b): PKCE (RFC 7636/9700) — verifier ÇAĞIRANDA (httpOnly çerez) kalır, URL'e
    yalnız S256 challenge girer. GitHub OAuth App'leri PKCE'yi resmî desteklemediği için
    yalnız  işaretli sağlayıcılarda gönderilir.
    """
    p = _PROVIDERS[provider]
    cid, secret = _creds(provider)
    sess = OAuth2Session(cid, secret, scope=p["scope"], redirect_uri=redirect_uri(provider))
    kwargs = {}
    if provider == "google":
        kwargs = {"access_type": "offline", "prompt": "consent"}
    if code_verifier and p.get("pkce"):
        kwargs["code_challenge"] = _code_challenge(code_verifier)
        kwargs["code_challenge_method"] = "S256"
    uri, _ = sess.create_authorization_url(p["authorize_url"], state=state, **kwargs)
    return uri


def exchange_code(provider: str, code: str, code_verifier: Optional[str] = None) -> dict:
    """code → token → userinfo. Normalize dict döner: {provider, sub, email, name}.

    Hata → ValueError (router 400'e çevirir). E-posta bulunamazsa ValueError.
    """
    p = _PROVIDERS[provider]
    cid, secret = _creds(provider)
    sess = OAuth2Session(cid, secret, redirect_uri=redirect_uri(provider))
    # GitHub token endpoint varsayılan form-encoded döner → JSON iste
    fetch_extra = {}
    if code_verifier and p.get("pkce"):
        fetch_extra["code_verifier"] = code_verifier  # BUG #185: PKCE dogrulamasi
    token = sess.fetch_token(
        p["token_url"],
        code=code,
        grant_type="authorization_code",
        **fetch_extra,
        headers={"Accept": "application/json"},
        timeout=_dis_cagri_timeout(),  # BUG #263: sınırsız asılma → havuz tükenmesi
    )
    if not token or not token.get("access_token"):
        raise ValueError(f"{provider}: access_token alınamadı")

    if provider == "google":
        info = sess.get(p["userinfo_url"], headers={"Accept": "application/json"},
                        timeout=_dis_cagri_timeout()).json()  # BUG #263
        email = (info.get("email") or "").lower().strip()
        if not email or not info.get("email_verified", True):
            raise ValueError("Google: doğrulanmış e-posta alınamadı")
        return {"provider": "google", "sub": str(info.get("sub")), "email": email,
                "name": info.get("name") or info.get("given_name")}

    # github
    info = sess.get(p["userinfo_url"], headers={"Accept": "application/vnd.github+json"},
                    timeout=_dis_cagri_timeout()).json()  # BUG #263
    email = (info.get("email") or "").lower().strip()
    if not email:
        # E-posta gizliyse /user/emails'ten birincil doğrulanmışı al
        emails = sess.get(p["emails_url"], headers={"Accept": "application/vnd.github+json"},
                          timeout=_dis_cagri_timeout()).json()  # BUG #263
        if isinstance(emails, list):
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
            verified = next((e for e in emails if e.get("verified")), None)
            chosen = primary or verified
            if chosen:
                email = (chosen.get("email") or "").lower().strip()
    if not email:
        raise ValueError("GitHub: doğrulanmış e-posta alınamadı (user:email izni gerekli)")
    return {"provider": "github", "sub": str(info.get("id")), "email": email,
            "name": info.get("name") or info.get("login")}
