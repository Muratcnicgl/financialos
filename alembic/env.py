from logging.config import fileConfig

from alembic import context

# FinancialOS: Base'i app.database'den al. Motor için ÖNCELİK SIRASI (BUG #196):
#   1) alembic config'te AÇIKÇA verilen `sqlalchemy.url` (programatik çağrı / test / tatbikat)
#   2) app.database.engine (.env'deki DATABASE_URL — normal CLI ve deploy yolu)
#
# BUG #196 (P5): eskiden config'teki URL KOŞULSUZ yok sayılıyordu. Sonuç: bir test veya
# script `Config.set_main_option("sqlalchemy.url", <geçici-db>)` verip `command.upgrade`
# çağırdığında migration GERÇEK veritabanına uygulanıyordu (canlı veri üstünde sessiz
# şema değişikliği riski). Bu yüzden "veri doluyken migration provası" yazılamıyordu.
from app.database import Base, engine as _varsayilan_engine


def _hedef_engine():
    """Config'te açık URL varsa ONU kullan; yoksa uygulamanın kendi motoru."""
    from sqlalchemy import create_engine as _ce
    try:
        acik_url = context.config.get_main_option("sqlalchemy.url", None)
    except Exception:
        acik_url = None
    # alembic.ini'deki placeholder (driver://user:pass@localhost/dbname) gerçek URL değildir
    if acik_url and "://" in acik_url and not acik_url.startswith("driver://"):
        if str(_varsayilan_engine.url) != acik_url:
            return _ce(acik_url)
    return _varsayilan_engine

# Tüm modellerin Base.metadata'ya kaydolması için import şart.
# Eksik import varsa autogenerate o tabloyu "DB'de var ama modelde yok" sanıp drop_table() üretir.
from app import models  # noqa: F401

# Alembic Config objesi - alembic.ini'yi okur.
config = context.config

# Logging config (alembic.ini'den)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate'in karşılaştırma yapacağı metadata
target_metadata = Base.metadata


def _compare_type_ignore_string_text(ctx, inspected_column, metadata_column, inspected_type, metadata_type):
    """SQLite reflection quirk: String <-> Text/VARCHAR farkı false positive üretir.

    SQLite'da String ve Text aynı type affinity'ye sahip (TEXT).
    Reflection sırasında String(N) -> TEXT olarak görünür, model String(N) ile karşılaştırılır.
    Bu fark bizim için anlamsız - SQLAlchemy/SQLite'ın bilinen davranışı.

    Diğer tip karşılaştırmaları default Alembic mantığı ile devam eder (None döndürerek).
    """
    from sqlalchemy import String, Text
    from sqlalchemy.dialects.sqlite import VARCHAR

    # String <-> Text/VARCHAR cosmetic farkı: ignore
    string_like = (String, Text, VARCHAR)
    if isinstance(inspected_type, string_like) and isinstance(metadata_type, string_like):
        return False  # "değişiklik yok" demek

    # Diğer tip karşılaştırmaları default mantığa bırak
    return None


def run_migrations_offline() -> None:
    """SQL script üretme modu - DB'ye bağlanmadan."""
    engine = _hedef_engine()   # BUG #196
    url = str(engine.url)
    # M50 (Wave-7): render_as_batch YALNIZ SQLite'ta. Postgres native ALTER destekler;
    # batch (tablo-recreate) Postgres'te gereksiz + inbound-FK'li tabloları kırabilir.
    is_sqlite = engine.url.get_backend_name() == "sqlite"
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Canlı DB'ye bağlanıp migration uygulama modu."""
    engine = _hedef_engine()   # BUG #196: config'te açık URL varsa o kullanılır
    with engine.connect() as connection:
        # M50: render_as_batch dialect-koşullu (SQLite ALTER kısıtı için, Postgres native).
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
            compare_type=_compare_type_ignore_string_text,  # SQLite String/Text false positive'i ignore et
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
