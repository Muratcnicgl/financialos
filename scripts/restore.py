"""
FinancialOS — yedekten GERİ YÜKLEME (P5 / H14).

"Yedekten geri yükleme provası yapılmadan yedek sayılmaz." Depoda `scripts/backup.py`
vardı ama **geri yükleme yoktu**: yedeğin gerçekten açılıp açılmadığı, şemanın güncel
olup olmadığı hiç denenmemişti. Felaket anında ilk kez denemek en kötü senaryodur.

Kullanım (SQLite — dev/tek-dosya kurulum):
    python -m scripts.restore --list
    python -m scripts.restore --from data/backups/2026-08-05-0130.db --dry-run
    python -m scripts.restore --from data/backups/2026-08-05-0130.db --confirm

Kullanım (PostgreSQL — production): bkz. `docs/deployment/runbook.md` §geri-yükleme.
Bu script Postgres URL'i görürse dosya kopyalamaz; doğru komutu yazdırır (yanlış
araçla veri kaybını önlemek için).

GÜVENLİK:
- `--confirm` olmadan HİÇBİR ŞEY yazılmaz (yıkıcı işlem, BUG #164 dersi).
- Geri yüklemeden önce mevcut DB'nin **güvenlik kopyası** alınır (yanlış yedeği
  yüklersen geri dönebilesin).
- Yedek dosyası önce `PRAGMA integrity_check` ile doğrulanır — bozuk yedek canlıyı ezmez.
- Geri yükleme sonrası tablo sayısı + alembic sürümü raporlanır (sessiz başarı yok).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = _REPO_ROOT / "data" / "backups"


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./data/financialos.db")


def _resolve_db_path(url: str) -> Path:
    raw = url[len("sqlite:///"):]
    p = Path(raw)
    return p if p.is_absolute() else (_REPO_ROOT / raw).resolve()


def dogrula(yedek: Path) -> tuple[bool, str]:
    """Yedek dosyası açılabiliyor ve bütünlük kontrolünden geçiyor mu?"""
    if not yedek.exists():
        return False, f"Yedek bulunamadi: {yedek}"
    if yedek.stat().st_size == 0:
        return False, "Yedek dosyasi BOS (0 bayt)"
    try:
        con = sqlite3.connect(f"file:{yedek}?mode=ro", uri=True)
        try:
            sonuc = con.execute("PRAGMA integrity_check").fetchone()
            if not sonuc or sonuc[0] != "ok":
                return False, f"Butunluk kontrolu BASARISIZ: {sonuc}"
            tablolar = con.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            if tablolar == 0:
                return False, "Yedekte hic tablo yok"
            try:
                surum = con.execute("SELECT version_num FROM alembic_version").fetchone()
                surum_s = surum[0] if surum else "yok"
            except sqlite3.Error:
                surum_s = "yok (alembic_version tablosu bulunamadi)"
            return True, f"OK — {tablolar} tablo, alembic surumu: {surum_s}"
        finally:
            con.close()
    except sqlite3.Error as e:
        return False, f"Yedek acilamadi: {type(e).__name__}: {e}"


def listele() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("*.db"), reverse=True)


def restore(yedek: Path, hedef: Path, dry_run: bool = True) -> int:
    ok, mesaj = dogrula(yedek)
    print(f"[dogrulama] {mesaj}")
    if not ok:
        print("IPTAL: bozuk/gecersiz yedek canli veriyi EZMEZ.")
        return 2

    if dry_run:
        print(f"[DRY-RUN] {yedek} -> {hedef} (degisiklik YOK). Uygulamak icin --confirm ekle.")
        return 0

    hedef.parent.mkdir(parents=True, exist_ok=True)
    if hedef.exists():
        emniyet = hedef.with_name(
            f"{hedef.stem}-pre-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")
        shutil.copy2(hedef, emniyet)
        print(f"[emniyet] mevcut DB kopyalandi: {emniyet}")

    shutil.copy2(yedek, hedef)
    ok2, mesaj2 = dogrula(hedef)
    print(f"[sonuc] geri yuklendi -> {hedef}")
    print(f"[dogrulama-sonrasi] {mesaj2}")
    return 0 if ok2 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Yedekten geri yukleme (YIKICI — --confirm gerekir)")
    ap.add_argument("--from", dest="kaynak", help="Yedek dosyasi yolu")
    ap.add_argument("--list", action="store_true", help="Mevcut yedekleri listele")
    ap.add_argument("--verify", help="Yalnizca yedegi dogrula (yazma yok)")
    ap.add_argument("--dry-run", action="store_true", help="Uygulamadan gosterir (varsayilan)")
    ap.add_argument("--confirm", action="store_true", help="GERCEKTEN geri yukle")
    args = ap.parse_args(argv)

    url = _database_url()
    if not url.startswith("sqlite:///"):
        print("PostgreSQL kurulumu tespit edildi. Bu script dosya kopyalamaz.\n"
              "Geri yukleme (production):\n"
              "  1) docker compose -f docker-compose.prod.yml stop backend scheduler\n"
              "  2) cat backup-YYYY-MM-DD.sql | docker compose -f docker-compose.prod.yml \\\n"
              "       exec -T db psql -U financialos -d financialos\n"
              "  3) docker compose -f docker-compose.prod.yml start backend scheduler\n"
              "  4) dogrulama: /api/health + kullanici sayisi + alembic surumu\n"
              "Ayrintili adimlar: docs/deployment/runbook.md")
        return 3

    hedef = _resolve_db_path(url)

    if args.list:
        yedekler = listele()
        if not yedekler:
            print(f"Yedek yok: {BACKUP_DIR}")
            return 1
        for y in yedekler:
            ok, mesaj = dogrula(y)
            isaret = "OK " if ok else "BOZUK"
            print(f"  [{isaret}] {y.name}  ({y.stat().st_size // 1024} KB)  {mesaj}")
        return 0

    if args.verify:
        ok, mesaj = dogrula(Path(args.verify))
        print(mesaj)
        return 0 if ok else 1

    if not args.kaynak:
        print("--from <yedek> gerekli (veya --list / --verify). Yikici islem: --confirm sart.")
        return 2

    return restore(Path(args.kaynak), hedef, dry_run=not args.confirm)


if __name__ == "__main__":
    sys.exit(main())
