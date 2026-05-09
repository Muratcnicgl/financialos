from logging.config import fileConfig

from alembic import context

# FinancialOS: Base ve engine'i app.database'den al, alembic.ini'deki URL'i bypass et.
# Bu şekilde tek doğruluk kaynağı app/database.py olur, .env'deki DATABASE_URL otomatik kullanılır.
from app.database import Base, engine

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
    url = str(engine.url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite için ALTER TABLE desteği
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Canlı DB'ye bağlanıp migration uygulama modu."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite için ALTER TABLE desteği (kolon ekleme/silme)
            compare_type=_compare_type_ignore_string_text,  # SQLite String/Text false positive'i ignore et
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
