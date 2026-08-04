"""
Dual-dialect (PostgreSQL) test kapısı koşucusu — docker'sız.

NEDEN: `tests/pg_gate.py` postgres yoksa testleri SKIP eder. "SQLite yeşil" bir kapı değildir
(ADR-038): RLS / Numeric / NULL-ordering davranışı yalnız Postgres'te doğrulanır. Bu script
gömülü `pgserver` binary'siyle yerel bir Postgres başlatır, PG_TEST_URL'i ayarlar, pytest'i
koşar ve sunucuyu kapatır — tek komut.

BİLİNEN TUZAK (ADR-038 / M49): Türkçe Windows locale (`Turkish_Türkiye.1254`) initdb'yi
0xC0000409 ile çökertir. pgserver initdb argümanlarını sabitlediği için cluster'ı BİZ
`--locale=C` ile kurarız; pgserver PG_VERSION dosyasını görüp initdb'yi atlar.

Kullanım:
    .\\venv\\Scripts\\python.exe scripts/pg_gate_run.py                    # tüm pg gate'leri
    .\\venv\\Scripts\\python.exe scripts/pg_gate_run.py tests/test_rls_postgres.py -q
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_TESTS = [
    "tests/test_rls_postgres.py",
    "tests/test_numeric_dual_dialect.py",
    "tests/test_net_worth_sign_source_m53.py",
    "tests/test_null_ordering_dual_dialect_m92.py",
    "tests/test_postgres_restore_drill.py",   # P5/H14: yedek→geri yükleme provası (prod yolu)
]


def _pgdata_dir() -> Path:
    d = os.getenv("PG_GATE_DATADIR")
    if d:
        return Path(d)
    return Path(tempfile.gettempdir()) / "financialos-pg-gate"


def ensure_cluster(pgdata: Path) -> None:
    """Cluster yoksa `initdb --locale=C` ile kur (Türkçe locale çökmesini atlatır)."""
    if (pgdata / "PG_VERSION").exists():
        return
    from pgserver._commands import initdb
    pgdata.mkdir(parents=True, exist_ok=True)
    print(f"[pg-gate] cluster kuruluyor (locale=C): {pgdata}")
    initdb(
        ["--auth=trust", "--auth-local=trust", "--encoding=utf8",
         "--locale=C", "-U", "postgres"],
        pgdata=pgdata,
    )


def main(argv: list[str]) -> int:
    import pgserver

    pgdata = _pgdata_dir()
    ensure_cluster(pgdata)

    print("[pg-gate] postgres baslatiliyor...")
    srv = pgserver.get_server(str(pgdata), cleanup_mode="stop")
    uri = srv.get_uri()
    print(f"[pg-gate] PG_TEST_URL={uri}")

    env = dict(os.environ, PG_TEST_URL=uri)
    tests = argv or DEFAULT_TESTS
    cmd = [sys.executable, "-m", "pytest", *tests, "-q"]
    print(f"[pg-gate] {' '.join(cmd)}")
    rc = subprocess.run(cmd, env=env).returncode
    print(f"[pg-gate] pytest cikis kodu: {rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
