"""
Dialect-aware veritabanı bağlantı katmanı (M49, Wave-7).
SQLAlchemy engine + session factory + Base metadata. **Hibrit:** dev SQLite / prod PostgreSQL.

`DATABASE_URL` dialect'ini tespit eder ve dialect'e göre engine kurar:
- **sqlite:** check_same_thread=False + BUG #060 PRAGMA listener (foreign_keys/WAL/busy_timeout/synchronous).
- **postgresql:** havuz config (pool_size/max_overflow/pool_pre_ping — PERF-014) + psycopg2 driver.

GUNCELLEMELER:
  BUG #060 fix: Her SQLite bağlantısında PRAGMA'lar (connect listener) — yalnız sqlite dialect'inde.
    foreign_keys=ON (DATA-003), journal_mode=WAL + busy_timeout (DATA-004, PERF-013), synchronous=NORMAL.
  M49 (Wave-7): dialect-aware — postgresql için pool_pre_ping (kopan bağlantı ölü-havuz önlenir) +
    pool_size/max_overflow (PERF-014). SQLite davranışı DEĞİŞMEDİ (mevcut testler korunur).
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, event, make_url
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Veritabanı konumu — varsayılan: data/financialos.db (dev). Prod: postgresql://... (DATABASE_URL).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/financialos.db")

# M49: dialect tespiti (sqlite | postgresql | ...) — SQLAlchemy URL parser'ı ile güvenli.
_DIALECT = make_url(DATABASE_URL).get_backend_name()  # 'sqlite' | 'postgresql' | ...
IS_SQLITE = _DIALECT == "sqlite"
IS_POSTGRES = _DIALECT in ("postgresql", "postgres")

# data/ klasörünü garanti et (yalnız dosya-tabanlı sqlite)
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# M49: dialect-aware engine kwargs
# BUG #244 (D29): SQLAlchemy istisna metinleri bound parameter'ları (ad, e-posta, şifre
# hash'i) taşıyordu ve bu metin traceback ile log'a/hata kaydına giriyordu. En sağlam
# savunma KAYNAKTA: parametreler istisnaya hiç girmesin (maskeleme ikinci katman kalır).
_engine_kwargs = {"echo": False, "hide_parameters": True}
if IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
elif IS_POSTGRES:
    # PERF-014: kopan bağlantıları önceden tespit et (pool_pre_ping) + makul havuz.
    # P5 (BUG #201) KAPASİTE: havuz PROCESS BAŞINADIR. Toplam bağlantı =
    #   WEB_CONCURRENCY × (pool_size + max_overflow) + scheduler(1×)
    # Bu toplam Postgres `max_connections` (varsayılan 100) sınırını AŞARSA uygulama
    # yük altında "too many connections" ile düşer — ve bu ancak canlıda görülür.
    # Varsayılan: 2 worker × (5+10) + scheduler 15 = 45 < 100 (güvenli).
    # Küçük VM'de (Oracle Free 1GB) havuzu env ile küçültmek gerekebilir.
    # BUG #263 (P5.5): yukarıdaki muhakeme YALNIZ Postgres `max_connections` tarafına
    # bakıyordu. Uygulamanın KENDİ eşzamanlılığı (anyio iş parçacığı havuzu, varsayılan 40)
    # bu 15'i kat kat aşıyordu → havuz uygulamanın içinde ÖNCE tükeniyordu. Hizalama ve
    # yavaş-yol tavanları `app/capacity.py`'de; burada yalnız bekleme süresi AÇIK yazılır:
    # örtük 30 sn, Docker HEALTHCHECK'ten uzun sürebilecek bir sessiz varsayılandı.
    _engine_kwargs.update(
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),  # 30 dk: bayat bağlantı kesilir
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "10")),    # BUG #263: örtük 30 sn yerine açık 10 sn
    )

engine = create_engine(DATABASE_URL, **_engine_kwargs)


# BUG #060 fix: Her yeni SQLite bağlantısında kritik PRAGMA'ları ayarla (YALNIZ sqlite dialect).
# SQLite'ta foreign_keys default KAPALI — ondelete=CASCADE/SET NULL tanımları aksi halde hiç
# çalışmaz (DATA-003). WAL + busy_timeout eşzamanlı yazımda "database is locked" önler (DATA-004,
# PERF-013). Postgres bunların HİÇBİRİNE gerek duymaz (FK default açık, MVCC ile kilit yok).
if IS_SQLITE:
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


# M51 (Wave-7): PostgreSQL RLS workspace-context hook. rules_engine.workspace_scope aktif workspace'i
# bir contextvar'da tutar; her transaction başında o değeri Postgres GUC'una (app.current_workspace_id)
# yazarız → RLS policy (ws_isolation) satırları DB-katmanında filtreler (2. savunma). Contextvar None ise
# (legacy/scope'suz) GUC yazılmaz → RLS "tümüne izin" (app-katmanı birincil). YALNIZ postgresql; SQLite no-op.
if IS_POSTGRES:
    from sqlalchemy import event as _event

    @_event.listens_for(SessionLocal, "after_begin")
    def _set_rls_workspace(session, transaction, connection):
        try:
            from app.rules_engine import _active_workspace  # lazy: circular import önle
            ws = _active_workspace.get()
        except Exception:
            ws = None
        if ws is not None:
            # SET LOCAL → yalnız bu transaction; parametreli set_config (SQL injection'sız)
            connection.exec_driver_sql(
                "SELECT set_config('app.current_workspace_id', %s, true)", (str(ws),)
            )

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


# BUG #311 fix (KAP-06): `init_db()` SİLİNDİ. İki ayrı gerekçe, ikisi de ölçüldü:
#   1. ÇAĞIRANI YOKTU. Docstring'i "setup_data.py'den çağrılır" diyordu; `setup_data.py`
#      `Base.metadata.drop_all/create_all`'ı DOĞRUDAN çağırıyor, `init_db`'yi değil
#      (`git grep init_db -- '*.py'` → yalnız tanım satırı). Yani docstring ölçülebilir
#      bir yalandı ve yanlışlığı hiçbir şeyi kırmadığı için 21 gün fark edilmedi.
#   2. ADR-013'E AYKIRIYDI. Şema otoritesi alembic'tir; `create_all` şemayı kurar ama
#      `alembic_version`'ı damgalamaz — sonraki `upgrade head` ya "table already exists"
#      der ya da belirsizliğe düşer. Tam olarak ADR-013 + ADR-013a'nın yasakladığı yol.
#      `docs/kalite-seruveni/dosya-denetimi/database.md` [DB-001] bunu 6 Ağu'da bulmuş,
#      "init_db'yi test-only yap" demiş; ölü olduğu için doğru cevap silmekti.