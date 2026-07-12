"""
SQLite veritabanı bağlantı katmanı.
SQLAlchemy engine + session factory + Base metadata.

GUNCELLEMELER:
  BUG #060 fix: Her SQLite bağlantısında PRAGMA'lar ayarlanır (connect listener).
    - foreign_keys=ON  → SQLite'ta FK enforcement default KAPALIYDI; modellerdeki
      ondelete=CASCADE/SET NULL tanımları hiç çalışmıyordu, yetim kayıt sessizce
      yazılabiliyordu (Kalite serüveni DATA-003).
    - journal_mode=WAL + busy_timeout → scheduler ve request eşzamanlı yazınca
      "database is locked" hatasını önler (DATA-004, PERF-013).
    - synchronous=NORMAL → WAL ile güvenli, daha hızlı.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, event
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


# BUG #060 fix: Her yeni SQLite bağlantısında kritik PRAGMA'ları ayarla.
# SQLite'ta foreign_keys default KAPALI — ondelete=CASCADE/SET NULL tanımları
# aksi halde hiç çalışmaz (DATA-003). WAL + busy_timeout eşzamanlı yazımda
# "database is locked" hatasını önler (DATA-004, PERF-013).
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()


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