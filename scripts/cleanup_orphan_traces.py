"""
Yetim / test-kullanıcı verisi temizliği (charter M3.1).

TARİHÇE (M3.1, Wave-2): Tek-kullanıcı MVP'sinde canlı DB'de üç user_id vardı — 1 "Murat"
(gerçek), 2 "test_user_decision_rhythm" (test), 3 (users tablosunda YOK, dangling-orphan).
Script bir kereliğine koşturuldu, 82 satır silindi (bkz. uygulanan-fixler.md M3.1).

GUNCELLEMELER:
  BUG #164 fix (P1, Wave-9 publish yolu — çok-kullanıcı denetimi): Script "gerçek kullanıcı =
    adı 'test' ile BAŞLAMAYAN" sezgisiyle çalışıyordu ve kalan HERKESİ (satırlarıyla birlikte)
    siliyordu. Bu, tek-kullanıcı döneminde zararsızdı; kapalı betada FELAKET: adı "Test..."/
    "testere" olan GERÇEK bir kullanıcının tüm finansal verisi + hesabı geri dönüşsüz silinirdi
    (SQLite LIKE büyük/küçük harf duyarsız, FK'lar PRAGMA ile kapatılıyor). Ayrıca çok-kullanıcılı
    bir DB'de "korunacaklar" listesine girmeyen her kullanıcı silinirdi.
    Yeni davranış: isim sezgisi TAMAMEN KALDIRILDI. Korunacak kullanıcı id'leri AÇIKÇA verilir
    (`--keep-user-ids`), silinecekler AÇIKÇA verilir (`--delete-user-ids`); ikisi de zorunlu ve
    kesişimleri boş olmalı. Ek olarak production ortamında `--force-production` şartı var.

Kullanım (yıkıcı — önce mutlaka --dry-run):
    .\\venv\\Scripts\\python.exe scripts/cleanup_orphan_traces.py \\
        --keep-user-ids 1,2,3 --delete-user-ids 7 --dry-run
"""
from __future__ import annotations

import argparse
import os
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


def _parse_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Yetim/test kullanıcı verisi temizliği (YIKICI — açık id listesi zorunlu)")
    parser.add_argument("--keep-user-ids", type=str, default=None,
                        help="Korunacak kullanıcı id'leri, virgülle (ZORUNLU)")
    parser.add_argument("--delete-user-ids", type=str, default=None,
                        help="Silinecek kullanıcı id'leri, virgülle (ZORUNLU). "
                             "Yetim satırlar için var olmayan id'ler de yazılabilir.")
    parser.add_argument("--dry-run", action="store_true", help="Hiçbir şey silme, sayıları göster")
    parser.add_argument("--force-production", action="store_true",
                        help="ENVIRONMENT=production ise ek onay")
    args = parser.parse_args(argv)

    keep = _parse_ids(args.keep_user_ids)
    delete = _parse_ids(args.delete_user_ids)

    # BUG #164: isim sezgisi YOK — açık liste yoksa hiçbir şey yapma.
    if not keep or not delete:
        print("IPTAL: --keep-user-ids ve --delete-user-ids ZORUNLU.\n"
              "  Bu script yikicidir; hangi kullanicinin silinecegini TAHMIN ETMEZ.\n"
              "  Once inceleyin:  SELECT id, name, email FROM users;")
        return 2

    kesisim = set(keep) & set(delete)
    if kesisim:
        print(f"IPTAL: ayni id hem korunacak hem silinecek listede: {sorted(kesisim)}")
        return 2

    if os.getenv("ENVIRONMENT", "").lower() == "production" and not args.force_production:
        print("IPTAL: production ortami. Bilincli isen --force-production ekle "
              "(ve once yedegi dogrula).")
        return 2

    ins = inspect(engine)
    with engine.connect() as c:
        mevcut = {r[0]: r[1] for r in c.execute(text("SELECT id, name FROM users"))}

    # Korunacak id gerçekten var mı? (yanlış id ile "herkesi sil" senaryosunu engeller)
    eksik_keep = [i for i in keep if i not in mevcut]
    if eksik_keep:
        print(f"IPTAL: korunacak id'ler DB'de yok: {eksik_keep} — yanlis liste vermis olabilirsin.")
        return 2

    print(f"DB'deki kullanicilar : {mevcut}")
    print(f"Korunacak (dokunulmaz): {keep}")
    print(f"Silinecek             : {delete}")

    user_tables = [t for t in ins.get_table_names()
                   if t != "users" and any(col["name"] == "user_id" for col in ins.get_columns(t))]

    del_csv = ",".join(str(i) for i in delete)
    total = 0
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))  # maintenance: FK sirasindan bagimsiz sil
        for t in sorted(user_tables):
            n = c.execute(text(f"SELECT COUNT(*) FROM {t} WHERE user_id IN ({del_csv})")).scalar()
            if n:
                print(f"  {t}: {n} satir" + (" [DRY]" if args.dry_run else " -> siliniyor"))
                if not args.dry_run:
                    c.execute(text(f"DELETE FROM {t} WHERE user_id IN ({del_csv})"))
                total += n
        n = c.execute(text(f"SELECT COUNT(*) FROM users WHERE id IN ({del_csv})")).scalar()
        if n:
            print(f"  users: {n} kullanici" + (" [DRY]" if args.dry_run else " -> siliniyor"))
            if not args.dry_run:
                c.execute(text(f"DELETE FROM users WHERE id IN ({del_csv})"))
            total += n

    if args.dry_run:
        print(f"\nDRY-RUN: {total} satir silinecekti (degisiklik YOK).")
        return 0
    print(f"\nOK: {total} satir silindi.")
    return 0


if __name__ == "__main__":
    bk = _backup()
    if bk:
        print(f"Yedek: {bk}\n")
    raise SystemExit(main())
