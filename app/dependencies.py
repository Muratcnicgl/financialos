"""
FastAPI bagimliliklari (dependencies).

Her router DB session ve aktif kullanici gibi ortak ihtiyaclari
buradan import eder. Tek user MVP icin User.id=1 varsayimi var,
ileride JWT eklenince get_current_user gercek auth'a baglanir.
"""

from typing import Generator
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User


def get_db() -> Generator[Session, None, None]:
    """Her istekte taze SQLAlchemy session uretir, istek bitince kapatir."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    M11 (ADR-033): JWT auth + geriye-uyum fallback.

    - `Authorization: Bearer <access-token>` varsa → JWT doğrula, user'ı DB'den çek.
    - Token yok + `AUTH_ENABLED` kapalı (default) → tek-kullanıcı fallback (ilk User).
      Mevcut 817 test + tek-kullanıcı lokal kurulum bu yolu kullanır (kırılmaz).
    - Token yok + `AUTH_ENABLED` açık → 401 (multi-user prod).

    Mimari sınır: auth SADECE burada bağlanır (app/PROJE.md).
    """
    # Geç import: auth modülü (SECRET_KEY) yalnız gerektiğinde yüklensin
    from app import auth as _auth
    import jwt as _jwt

    header = request.headers.get("Authorization", "")
    token = header[7:].strip() if header.startswith("Bearer ") else ""

    if token:
        try:
            payload = _auth.decode_token(token, expected_type="access")
        except _jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz veya süresi geçmiş token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = db.get(User, int(payload["sub"]))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Kullanıcı bulunamadı veya pasif.",
            )
        return user

    if _auth.auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekli (Authorization: Bearer <token>).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Geriye-uyum: tek-kullanıcı fallback
    user = db.query(User).order_by(User.id.asc()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanici kurulumu yapilmamis. POST /api/user ile olusturun "
                   "veya scripts/setup_data.py calistirin.",
        )
    return user