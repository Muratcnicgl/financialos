"""
P5 (Wave-9) — H14 (prod yolu): PostgreSQL yedek/geri-yükleme PROVASI.

`tests/test_backup_restore_drill.py` SQLite (dev) yolunu kanıtlar. Production
**PostgreSQL** kullanır (ADR-038) ve runbook'ta yalnız tek bir `pg_dump` satırı vardı:
geri yükleme adımı yazılmamış, hiç DENENMEMİŞTİ. Yanlış yolu felaket anında öğrenmek
kabul edilemez.

Bu tatbikat gerçek `pg_dump` + `psql` ikililerini kullanır:
    veri yaz → dump al → **veritabanını düşür** → yeniden yarat → restore → veri aynı mı?

PostgreSQL erişilemezse SKIP (SQLite süiti bloklanmaz) — `scripts/pg_gate_run.py` ile koşulur.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.pg_gate import postgres_url_or_skip, fresh_pg_database


def _pg_bin(ad: str) -> str:
    """Gömülü pgserver ikilisi (pg_dump/psql) — sistemde postgres kurulu olmasa da çalışır."""
    try:
        import pgserver
        yol = Path(pgserver.__file__).parent / "pginstall" / "bin" / f"{ad}.exe"
        if yol.exists():
            return str(yol)
        yol = Path(pgserver.__file__).parent / "pginstall" / "bin" / ad
        if yol.exists():
            return str(yol)
    except Exception:
        pass
    return ad  # PATH'te varsayılır


def _kos(cmd: list[str], stdin_dosya=None, stdout_dosya=None) -> int:
    return subprocess.run(cmd, stdin=stdin_dosya, stdout=stdout_dosya,
                          stderr=subprocess.PIPE).returncode


def test_postgres_dump_restore_provasi(tmp_path):
    base_url = postgres_url_or_skip()
    db_url = fresh_pg_database(base_url, "fos_restore_drill")

    eng = create_engine(db_url)
    with eng.begin() as c:
        c.execute(text("CREATE TABLE accounts (id INT PRIMARY KEY, name TEXT, balance NUMERIC(19,4))"))
        c.execute(text("INSERT INTO accounts VALUES (1,'Maaş Hesabım',12345.6700),"
                       "(2,'Kredi Kartım',-4200.0000)"))
    eng.dispose()

    # --- YEDEK (runbook'taki pg_dump adımının birebir karşılığı) ---
    dump = tmp_path / "yedek.sql"
    with open(dump, "wb") as f:
        rc = _kos([_pg_bin("pg_dump"), "--dbname", db_url, "--no-owner"], stdout_dosya=f)
    assert rc == 0, "pg_dump başarısız"
    assert dump.stat().st_size > 0, "Dump dosyası boş"

    # --- FELAKET: veritabanı düşürülür ---
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text('DROP DATABASE IF EXISTS "fos_restore_drill" WITH (FORCE)'))
        c.execute(text('CREATE DATABASE "fos_restore_drill"'))
    admin.dispose()

    # Boş mu? (tatbikat gerçekten yıkıcı olmalı, aksi hâlde kanıt değil)
    eng = create_engine(db_url)
    with eng.connect() as c:
        var_mi = c.execute(text(
            "SELECT to_regclass('public.accounts') IS NOT NULL")).scalar()
    eng.dispose()
    assert var_mi is False, "Tatbikat yıkıcı değil — tablo hâlâ duruyor"

    # --- GERİ YÜKLEME ---
    with open(dump, "rb") as f:
        rc = _kos([_pg_bin("psql"), "--dbname", db_url, "-v", "ON_ERROR_STOP=1", "-q"],
                  stdin_dosya=f)
    assert rc == 0, "psql ile geri yükleme başarısız"

    # --- DOĞRULAMA: veri birebir aynı mı? ---
    eng = create_engine(db_url)
    with eng.connect() as c:
        satirlar = c.execute(text("SELECT id, name, balance FROM accounts ORDER BY id")).fetchall()
    eng.dispose()

    assert [(r[0], r[1], float(r[2])) for r in satirlar] == [
        (1, "Maaş Hesabım", 12345.67), (2, "Kredi Kartım", -4200.0)
    ], f"Geri yüklenen veri farklı: {satirlar}"


def test_runbook_geri_yukleme_adimini_belgeler():
    """Prova kadar önemli: felaket anında bakılacak yazılı adım VAR olmalı."""
    kok = Path(__file__).resolve().parent.parent
    runbook = (kok / "docs" / "deployment" / "runbook.md").read_text(encoding="utf-8").lower()
    assert "pg_dump" in runbook, "Runbook yedek adımını belgelemiyor"
    assert "psql" in runbook and "geri yükle" in runbook, (
        "Runbook GERİ YÜKLEME adımını belgelemiyor — yedek tek başına güvence değildir"
    )
