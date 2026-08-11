"""
M49 (Wave-7) — PostgreSQL gate yardımcısı (dual-dialect testler için).

Wave-7 KRİTİK CANLI-GATE: "SQLite yeşil" yetmez, gate'ler Postgres'te de koşmalı. Bu ortamda docker
YOK → `pgserver` (bundled postgres binary wheel) ile docker'sız postgres. Türkçe locale initdb'yi
0xC0000409 ile çökertiyor → **--locale=C** ile çözülür (M49 keşfi).

Kullanım (dual-dialect test):
    from tests.pg_gate import postgres_url_or_skip
    def test_x():
        url = postgres_url_or_skip()          # postgres yoksa test SKIP
        eng = create_engine(url)
        ...

Çalışan postgres kaynağı (öncelik):
1. env `PG_TEST_URL` (CI: GitHub Actions postgres service veya compose db).
2. Yerel pgserver instance (localhost:5433) — bu oturumda arka planda koşuyor.
Hiçbiri ulaşılamazsa `pytest.skip` (ana SQLite süiti bloklanmaz).
"""
from __future__ import annotations

import os
import pytest
from sqlalchemy import create_engine, text

_DEFAULT_LOCAL = "postgresql://postgres@localhost:5433/postgres"


def get_postgres_url() -> str | None:
    """Ulaşılabilir bir postgres DATABASE_URL döner; yoksa None."""
    for url in (os.getenv("PG_TEST_URL"), _DEFAULT_LOCAL):
        if not url:
            continue
        try:
            eng = create_engine(url, connect_args={"connect_timeout": 3})
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            eng.dispose()
            return url
        except Exception:
            continue
    return None


def postgres_url_or_skip() -> str:
    """Postgres URL döner; ulaşılamazsa testi SKIP eder (dual-dialect gate'ler için)."""
    url = get_postgres_url()
    if url is None:
        pytest.skip("PostgreSQL erişilemiyor (PG_TEST_URL veya yerel pgserver:5433 gerekli) — dual-dialect gate atlandı")
    return url


def fresh_pg_database(base_url: str, name: str) -> str:
    """Verilen postgres sunucusunda temiz bir test veritabanı oluşturur, URL'ini döner.
    (Var olanı düşürüp yeniden yaratır — izole gate koşumu için.)"""
    from sqlalchemy import create_engine as _ce
    admin = _ce(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        # BUG #238: bir gate testi yarıda kalınca (assert patlaması) bağlantıları açık
        # bırakıyordu; sonraki testin DROP DATABASE'i "is being accessed by other users"
        # ile ölüp ARDIŞIK ERROR zinciri üretiyordu — gerçek arıza kaybolur. Önce artık
        # oturumları düşür, sonra düşür.
        conn.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": name})
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    # base_url'in veritabanı adını değiştir
    from sqlalchemy.engine import make_url
    # BUG #300: burada `str(url)` vardı — SQLAlchemy'nin `URL.__str__()` şifreyi
    # **maskeler** (`postgres:***@...`). Dönen URL ile kurulan her bağlantı
    # "password authentication failed" alır. Yerelde görünmez, çünkü yerel `pgserver`
    # `trust` kimlik doğrulamasıyla açılır ve şifreyi hiç sormaz; şifre isteyen her
    # gerçek Postgres'te (CI servisi, prod) sessizce çöker.
    return make_url(base_url).set(database=name).render_as_string(hide_password=False)


def test_pg_gate_ortami():
    """M49 kanıtı: postgres erişilebilirse dialect + Numeric(19,4) round-trip doğrula (yoksa skip)."""
    url = postgres_url_or_skip()
    eng = create_engine(url)
    with eng.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
        conn.execute(text("DROP TABLE IF EXISTS _pg_gate_t"))
        conn.execute(text("CREATE TABLE _pg_gate_t(v numeric(19,4))"))
        conn.execute(text("INSERT INTO _pg_gate_t VALUES (123.4567)"))
        v = conn.execute(text("SELECT v FROM _pg_gate_t")).scalar()
        conn.execute(text("DROP TABLE _pg_gate_t"))
        conn.commit()
        from decimal import Decimal
        assert v == Decimal("123.4567")
    eng.dispose()
    assert eng.dialect.name == "postgresql"
