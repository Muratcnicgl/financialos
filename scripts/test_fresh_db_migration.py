"""
Temiz-DB kurulum testi (charter M1 — ADR-013 tam gerçekleştirme).

Bomboş bir SQLite dosyasında `alembic upgrade head` çalıştırıldığında TÜM şema kurulmalı ve
sonuç `Base.metadata.create_all` ile ÖZDEŞ olmalı. Bu, `git clone` + `alembic upgrade head`
ile yeni ortam kurulumunu (Wave-3 open-source/multi-user; Firefly/Beancount/Maybe sektör
pratiği) garanti eder.

TARİHÇE: Eskiden migration zinciri sıfırdan-şema DEĞİLdi (`baseline_existing_schema` bir
STAMP'ti, taban `create_all` ile kurulurdu; bomboş DB'de `alembic upgrade head` çökerdi —
coach_insights var-olmadan batch_alter edilirdi). M1'de non-destructive collapse yapıldı:
tek `b70779a2f621_genesis_full_schema` tüm 21 tabloyu (+48 index) yaratır (root); sonraki
migration'lar zincir sürekliliği için no-op'a indirildi. Canlı DB etkilenmedi (genesis onun
atasıdır, yeniden çalışmaz). Artık temiz-DB kurulumu DESTEKLENİYOR ve bu test onu kilitler.

Kullanım:  .\venv\Scripts\python.exe scripts/test_fresh_db_migration.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _schema(db_url: str):
    from sqlalchemy import create_engine, inspect
    e = create_engine(db_url)
    ins = inspect(e)
    out = {}
    for t in ins.get_table_names():
        if t == "alembic_version":
            continue
        cols = frozenset(c["name"] for c in ins.get_columns(t))
        idx = frozenset(i["name"] for i in ins.get_indexes(t))
        out[t] = (cols, idx)
    e.dispose()
    return out


def main() -> int:
    from sqlalchemy import create_engine
    from app import models  # noqa: F401 — Base.metadata dolsun
    from app.models import Base

    td = Path(tempfile.mkdtemp(prefix="fresh_db_"))

    # A) Bomboş DB'ye alembic upgrade head
    dba = td / "alembic.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{dba.as_posix()}"}
    # encoding acikca UTF-8: Windows'ta `text=True` yerel kod sayfasini (cp1254) kullanir ve
    # Turkce baslikli migration mesajlari okuma is parcaciginda UnicodeDecodeError firlatir —
    # kontrol yine tamamlaniyordu ama CIKTISI okunamiyordu (BUG #274 turunda goruldu).
    p = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=REPO_ROOT, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print("FAIL: temiz DB'de 'alembic upgrade head' basarisiz")
        print(p.stdout[-1500:]); print(p.stderr[-1500:])
        return 1

    # B) create_all referansı
    dbb = td / "createall.db"
    Base.metadata.create_all(create_engine(f"sqlite:///{dbb.as_posix()}"))

    sa, sb = _schema(f"sqlite:///{dba.as_posix()}"), _schema(f"sqlite:///{dbb.as_posix()}")
    if set(sa) != set(sb):
        print(f"FAIL: tablo farki — alembic-eksik={set(sb)-set(sa)} fazla={set(sa)-set(sb)}")
        return 1
    diffs = [t for t in sa if sa[t] != sb[t]]
    if diffs:
        print("FAIL: sema (kolon/index) farki:")
        for t in diffs:
            print(f"  {t}: kolon_farki={sb[t][0] ^ sa[t][0]} index_farki={sb[t][1] ^ sa[t][1]}")
        return 1

    assert "envelopes" in sa and "wishlist_items" in sa and "coach_insights" in sa
    print(f"OK: temiz DB'de 'alembic upgrade head' {len(sa)} tabloyu kurdu; "
          f"sema create_all ile TAM OZDES (kolon + index). ADR-013 temiz-kurulum destegi dogrulandi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
