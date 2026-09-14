"""
SQLite yedekleme çekirdeği — TEK KAYNAK (DEVOPS-010 / BUG #494).

Önce `scripts/backup.py`de yaşıyordu ve YALNIZ elle ya da Windows Görev Zamanlayıcı'dan
(`gorevleri_kur.ps1`) çağrılıyordu: yedek, kurulum adımına bağlıydı — görevi kurmayan bir
makinede (ya da görev sessizce silindiğinde) hiç yedek alınmıyordu ve bunu ölçen yoktu.
Çekirdek uygulamaya taşındı: `app/scheduler.py` SQLite'ta her gece 03:15 bu fonksiyonu
koşturur ve çalışma kaydı (`SchedulerRun`) bırakır — yedeğin ölmesi görünür olur. CLI
(`python -m scripts.backup`) aynı çekirdeği çağırır (uygulama `scripts/`e bağımlı olmaz — BE-033).

Değişmezler (SBK-001…007, `scripts/backup.py` tarihçesi):
  - çevrimiçi yedek (`sqlite3.Connection.backup`) + `PRAGMA integrity_check`,
  - saniye damgası + var olanı ezmeme,
  - bozuk/yarım kopya silinir, hata YÜKSELİR (sessiz "başarılı" yok),
  - saklama: `keep_days`ten eski yedekler silinir; az önce alınan ASLA silinmez.
"""
from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

REPO_KOK = Path(__file__).resolve().parent.parent


class YedekHatasi(RuntimeError):
    """Yedek alınamadı — çağıran (CLI/scheduler) bunu görünür yapar."""


def sqlite_db_yolu(url: str | None = None) -> Path:
    """DATABASE_URL'den SQLite dosya yolu; SQLite değilse YedekHatasi."""
    url = url or os.getenv("DATABASE_URL", "sqlite:///./data/financialos.db")
    if not url.startswith("sqlite:///"):
        raise YedekHatasi(f"SQLite yedeği yalnız sqlite:/// için; DATABASE_URL={url!r}")
    raw = url[len("sqlite:///"):]
    p = Path(raw)
    return p if p.is_absolute() else (REPO_KOK / raw).resolve()


def varsayilan_yedek_dizini() -> Path:
    return REPO_KOK / "data" / "backups"


def sqlite_yedekle(db_yolu: Path, yedek_dizini: Path, keep_days: int = 30) -> tuple[Path, int]:
    """Yedek alır, eskileri temizler. (yedek dosyası, silinen eski yedek sayısı) döner."""
    if keep_days < 0:
        raise YedekHatasi(f"keep_days negatif olamaz (verilen: {keep_days}).")
    if not db_yolu.exists():
        raise YedekHatasi(f"DB bulunamadı: {db_yolu}")
    yedek_dizini.mkdir(parents=True, exist_ok=True)

    damga = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    hedef = yedek_dizini / f"{damga}.db"
    n = 1
    while hedef.exists():
        hedef = yedek_dizini / f"{damga}-{n}.db"
        n += 1

    kaynak = dest = None
    try:
        kaynak = sqlite3.connect(str(db_yolu))
        dest = sqlite3.connect(str(hedef))
        kaynak.backup(dest)
        satir = dest.execute("PRAGMA integrity_check").fetchone()
        if not satir or satir[0] != "ok":
            raise sqlite3.DatabaseError(f"integrity_check başarısız: {satir}")
    except sqlite3.Error as e:
        if dest:
            dest.close()
        if kaynak:
            kaynak.close()
        try:
            if hedef.exists():
                hedef.unlink()   # yarım/bozuk kopya kalmasın
        except OSError:
            pass
        raise YedekHatasi(f"yedekleme başarısız: {e}") from e
    finally:
        if dest:
            dest.close()
        if kaynak:
            kaynak.close()

    esik = time.time() - keep_days * 86400
    eskiler = [f for f in yedek_dizini.glob("*.db")
               if f.resolve() != hedef.resolve() and f.stat().st_mtime < esik]
    for f in eskiler:
        f.unlink()
    return hedef, len(eskiler)
