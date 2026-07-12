"""
Envelope + WishlistItem migration testi (charter M1.6).

BULGU (KURAL R3 — disk gerçeği charter varsayımını düzeltti): Bu projede migration zinciri
SIFIRDAN-şema DEĞİL. `fa46373f4ca8_baseline_existing_schema` bir STAMP noktasıdır; taban şema
`Base.metadata.create_all` (init_db / setup_data) ile kurulur, Alembic yalnız artımlı
değişiklikleri izler. Bu yüzden bomboş bir DB'de `alembic upgrade head` çöker
(ör. `extend_coach_insights` var-olmayan tabloyu batch_alter eder). "Temiz DB'den saf-alembic"
bu projede DESTEKLENMEZ (ADR-013 kısmen gerçekleşmiş; bkz. milestone-log.md M1 notu).

Bu test GERÇEK senaryoyu doğrular — canlı DB'nin birebir durumu:
  taban şema VAR (create_all) + envelopes/wishlist_items YOK + revizyon down_revision'da
  → `alembic upgrade head` iki tabloyu YARATIR.

Kullanım:  .\venv\Scripts\python.exe scripts/test_fresh_db_migration.py
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))   # scripts/ dizininden çalışınca app importlanabilsin
DOWN_REVISION = "f3dda4d3996d"   # envelope migration'ından bir önceki head


def _tables(db: Path) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="mig_test_")) / "scenario.db"
    url = f"sqlite:///{tmp.as_posix()}"
    env = {**os.environ, "DATABASE_URL": url}

    # 1) Taban şemayı create_all ile kur (projenin gerçek bootstrap yolu)
    from sqlalchemy import create_engine, text
    from app import models  # noqa: F401  — tüm modeller Base.metadata'ya kayıtlı olsun
    from app.models import Base

    eng = create_engine(url)
    Base.metadata.create_all(eng)

    # 2) Canlı DB durumunu taklit et: envelopes + wishlist_items YOK, revizyon down_revision'da
    with eng.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS wishlist_items"))
        c.execute(text("DROP TABLE IF EXISTS envelopes"))
    eng.dispose()

    before = _tables(tmp)
    assert "envelopes" not in before and "wishlist_items" not in before, "kurulum: tablolar drop edilmeliydi"
    assert "accounts" in before and "coach_insights" in before, "kurulum: taban şema olmalı"

    # 3) Alembic'i down_revision'da damgala, sonra head'e yükselt
    for args in (["stamp", DOWN_REVISION], ["upgrade", "head"]):
        p = subprocess.run([sys.executable, "-m", "alembic", *args],
                           cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        if p.returncode != 0:
            print(f"FAIL: alembic {' '.join(args)} basarisiz")
            print(p.stdout[-1500:]); print(p.stderr[-1500:])
            return 1

    # 4) Doğrula: iki tablo migration ile yaratıldı
    after = _tables(tmp)
    missing = {"envelopes", "wishlist_items"} - after
    if missing:
        print(f"FAIL: migration sonrasi hala eksik: {sorted(missing)}")
        return 1

    print(f"OK: taban-sema-var + tablolar-yok DB'de 'alembic upgrade head' "
          f"envelopes + wishlist_items YARATTI (canli DB senaryosu dogrulandi).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
