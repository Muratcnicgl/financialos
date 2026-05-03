"""
FastAPI bagimliliklari (dependencies).

Her router DB session ve aktif kullanici gibi ortak ihtiyaclari
buradan import eder. Tek user MVP icin User.id=1 varsayimi var,
ileride JWT eklenince get_current_user gercek auth'a baglanir.
"""

from typing import Generator
from fastapi import Depends, HTTPException, status
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


def get_current_user(db: Session = Depends(get_db)) -> User:
    """
    Tek-kullanici MVP: ilk olusturulan User'i doner.
    User yoksa 404 verir (kurulum yapilmasi gerektigini soyler).

    Production'a gecince burasi JWT auth'a baglanir, soyle:
        token = Depends(oauth2_scheme)
        payload = jwt.decode(token, ...)
        user = db.query(User).get(payload['sub'])
    """
    user = db.query(User).order_by(User.id.asc()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanici kurulumu yapilmamis. POST /api/user ile olusturun "
                   "veya scripts/setup_data.py calistirin.",
        )
    return user