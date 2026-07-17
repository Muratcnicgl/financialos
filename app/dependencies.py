"""
FastAPI bagimliliklari (dependencies).

Her router DB session ve aktif kullanici gibi ortak ihtiyaclari
buradan import eder. Tek user MVP icin User.id=1 varsayimi var,
ileride JWT eklenince get_current_user gercek auth'a baglanir.
"""

import logging
from typing import Generator
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """Her istekte taze SQLAlchemy session uretir, istek bitince kapatir."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _fallback_user(db: Session) -> User:
    """Geriye-uyum: tek-kullanıcı fallback (ilk User). AUTH_ENABLED kapalı yolun sonu."""
    user = db.query(User).order_by(User.id.asc()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanici kurulumu yapilmamis. POST /api/user ile olusturun "
                   "veya scripts/setup_data.py calistirin.",
        )
    return user


def _unauthorized(code: str, message: str) -> HTTPException:
    """401 — gövdede makine-okunur `code` (frontend token_expired'ı ayırt etsin, BUG #158)."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    M11 (ADR-033) + M61 (BUG #158): JWT auth + geriye-uyum fallback.

    - `Authorization: Bearer <access-token>` geçerliyse → user'ı DB'den çek.
    - Token GEÇERSIZ/SÜRESİ GEÇMİŞ:
        · `AUTH_ENABLED` açık → 401 `{code: "token_expired"}` (frontend refresh/login'e gider).
        · `AUTH_ENABLED` kapalı → **401 ATMA**, sessizce fallback'e düş (BUG #158: ölü token
          uygulamayı KİLİTLEMESİN — lokal/tek-kullanıcı kurulum çürük token'la boğulmaz).
    - Token yok:
        · `AUTH_ENABLED` açık → 401 `{code: "auth_required"}`.
        · kapalı → tek-kullanıcı fallback.

    Mimari sınır: auth SADECE burada bağlanır (app/PROJE.md).
    """
    # Geç import: auth modülü (SECRET_KEY) yalnız gerektiğinde yüklensin
    from app import auth as _auth
    import jwt as _jwt

    auth_on = _auth.auth_enabled()
    header = request.headers.get("Authorization", "")
    token = header[7:].strip() if header.startswith("Bearer ") else ""

    if token:
        try:
            payload = _auth.decode_token(token, expected_type="access")
            user = db.get(User, int(payload["sub"]))
            if not user or not user.is_active:
                raise _jwt.InvalidTokenError("user not found or inactive")
            return user
        except _jwt.PyJWTError:
            # M61 (BUG #158): auth kapalıyken bozuk token uygulamayı kilitlemesin
            if auth_on:
                raise _unauthorized("token_expired", "Geçersiz veya süresi geçmiş token.")
            logger.info("[auth] geçersiz token yok sayıldı (AUTH_ENABLED kapalı) → fallback")
            return _fallback_user(db)

    if auth_on:
        raise _unauthorized("auth_required", "Kimlik doğrulama gerekli (Authorization: Bearer <token>).")

    return _fallback_user(db)