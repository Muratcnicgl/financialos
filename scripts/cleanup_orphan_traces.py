"""
Yetim / test-kullanıcı verisi temizliği (charter M3.1).

BULGU (R3, disk gerçeği memory'yi düzeltti): Tek-kullanıcı MVP'sinde canlı DB'de üç user_id var:
  - user_id=1 "Murat" → GERÇEK kullanıcı (korunur)
  - user_id=2 "test_user_decision_rhythm" → TEST kullanıcı (isim açık), 56 reasoning_trace + 4 coach_insight
  - user_id=3 → users tablosunda YOK (dangling/orphan), 20 reasoning_trace (20 May dev oturumu, jenerik test içeriği)
Memory "20 yetim (user_id=2)" diyordu; gerçekte 2=test-kullanıcı, 3=dangling-orphan. İkisi de 20 May
dev pollution → single-user bütünlüğünü bozuyor (FK açıkken user_id=3 integrity ihlali).

KARAR (charter M3.1 + K10): GERÇEK kullanıcı = ismi 'test' ile başlamayan. Diğer TÜM user-scoped
tablolardaki gerçek-olmayan (test + orphan) satırlar + test user satırları silinir. İdempotent
(tekrar çalıştırılırsa 0 siler). Silmeden önce YEDEK alınır.

Kullanım:  .\venv\Scripts\python.exe scripts/cleanup_orphan_traces.py [--dry-run]
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402
from app.database import engine, DATABASE_URL  # noqa: E402


def _backup() -> Path | None:
    if not DATABASE_URL.startswith("sqlite:///"):
        return None
    src = Path(DATABASE_URL.replace("sqlite:///", ""))
    if not src.exists():
        return None
    bdir = Path("backups"); bdir.mkdir(exist_ok=True)
    dest = bdir / f"{src.stem}-pre-cleanup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy2(src, dest)
    return dest


def main() -> int:
    dry = "--dry-run" in sys.argv
    ins = inspect(engine)

    with engine.connect() as c:
        real_ids = [r[0] for r in c.execute(
            text("SELECT id FROM users WHERE name NOT LIKE 'test%'"))]
        test_user_ids = [r[0] for r in c.execute(
            text("SELECT id FROM users WHERE name LIKE 'test%'"))]
    if not real_ids:
        print("GUVENLIK: gercek kullanici bulunamadi — iptal.")
        return 1
    print(f"Gercek kullanici id'leri (korunacak): {real_ids}")
    print(f"Test kullanici id'leri (silinecek): {test_user_ids}")

    # user_id sutunu olan tum tablolar
    user_tables = [t for t in ins.get_table_names()
                   if t != "users" and any(col["name"] == "user_id" for col in ins.get_columns(t))]

    real_csv = ",".join(str(i) for i in real_ids)
    total = 0
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))  # maintenance: FK sirasindan bagimsiz sil
        for t in sorted(user_tables):
            n = c.execute(text(f"SELECT COUNT(*) FROM {t} WHERE user_id NOT IN ({real_csv})")).scalar()
            if n:
                print(f"  {t}: {n} gercek-olmayan satir (test+orphan)" + (" [DRY]" if dry else " -> siliniyor"))
                if not dry:
                    c.execute(text(f"DELETE FROM {t} WHERE user_id NOT IN ({real_csv})"))
                total += n
        # test user satirlarini sil
        if test_user_ids:
            tu = ",".join(str(i) for i in test_user_ids)
            n = c.execute(text(f"SELECT COUNT(*) FROM users WHERE id IN ({tu})")).scalar()
            print(f"  users: {n} test kullanici" + (" [DRY]" if dry else " -> siliniyor"))
            if not dry:
                c.execute(text(f"DELETE FROM users WHERE id IN ({tu})"))
            total += n
        if dry:
            raise SystemExit(f"DRY-RUN: {total} satir silinecekti (degisiklik yok).")

    print(f"\nOK: {total} gercek-olmayan satir silindi (test-kullanici + orphan). Single-user butunlugu saglandi.")
    return 0


if __name__ == "__main__":
    bk = _backup()
    if bk:
        print(f"Yedek: {bk}\n")
    raise SystemExit(main())
