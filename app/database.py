"""
SQLite veritabanı bağlantı katmanı.
SQLAlchemy engine + session factory + Base metadata.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Veritabanı konumu — varsayılan: data/financialos.db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/financialos.db")

# data/ klasörünü garanti et (yoksa oluştur)
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

# Engine — SQLite için check_same_thread=False (FastAPI çoklu thread kullanır)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,  # SQL loglarını görmek istersen True yap
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Tüm modellerin türeyeceği taban sınıf
Base = declarative_base()


def get_db() -> Session:
    """
    FastAPI dependency injection için DB oturumu sağlayıcı.
    Kullanım: def endpoint(db: Session = Depends(get_db)):
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Tüm tabloları oluşturur. setup_data.py'den çağrılır.
    Var olan tablolara dokunmaz (CREATE IF NOT EXISTS).
    """
    # Tüm modelleri import et ki Base.metadata onları görsün
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)