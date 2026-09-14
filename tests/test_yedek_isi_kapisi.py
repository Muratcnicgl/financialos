"""
DEVOPS-010 (BUG #494): SQLite yedeği uygulamanın içinden alınır ve çalışma kaydı bırakır.

Ölçüm (14 Eyl 2026): yedek yalnız Windows Görev Zamanlayıcı'dan (`gorevleri_kur.ps1`) ya da
elle koşuyordu; görevi kurmayan makinede hiç yedek alınmıyor, bunu ölçen yoktu. Kilitlenen:
  1. `sqlite_backup` planlı iş SQLite'ta listede, izleme sarmalayıcısından geçer, 03:15
     (fiyat 02:45 ve gece batch 03:00'dan SONRA),
  2. iş koşunca gerçek bir yedek dosyası oluşur, kayıt `ok=True` ve `detail` yedek özetini taşır,
  3. çekirdek `app/yedek.py` (uygulama `scripts/`e bağımlı değil — BE-033); CLI aynı çekirdeği çağırır,
  4. bozuk kaynak → YedekHatasi (sessiz başarı yok), yarım kopya kalmaz.
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import scheduler as sched
from app import yedek
from app.models import Base, SchedulerRun

KOK = Path(__file__).resolve().parent.parent


def test_planli_isler_listesinde_ve_saati_dogru():
    plan = next((p for p in sched.PLANLI_ISLER if p.ad == "sqlite_backup"), None)
    assert plan is not None, "sqlite_backup planlı işlerde yok"
    assert getattr(plan.fonksiyon, "_izlenen_is_adi", None) == "sqlite_backup"
    assert plan.cron == {"hour": 3, "minute": 15}
    fiyat = next(p for p in sched.PLANLI_ISLER if p.ad == "fetch_investment_prices")
    batch = next(p for p in sched.PLANLI_ISLER if p.ad == "nightly_batch")
    dakika = lambda c: c["hour"] * 60 + c["minute"]  # noqa: E731
    assert dakika(plan.cron) > dakika(fiyat.cron) and dakika(plan.cron) > dakika(batch.cron)


def test_is_yedek_alir_ve_kayit_birakir(tmp_path, monkeypatch):
    kaynak = tmp_path / "canli.db"
    con = sqlite3.connect(kaynak); con.execute("CREATE TABLE t(x)"); con.execute("INSERT INTO t VALUES (1)"); con.commit(); con.close()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{kaynak.as_posix()}")
    monkeypatch.setattr(yedek, "varsayilan_yedek_dizini", lambda: tmp_path / "backups")
    # çalışma kaydı: bellek DB
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    monkeypatch.setattr(sched, "SessionLocal", lambda: s)
    plan = next(p for p in sched.PLANLI_ISLER if p.ad == "sqlite_backup")
    asyncio.run(plan.fonksiyon())
    dosyalar = list((tmp_path / "backups").glob("*.db"))
    assert len(dosyalar) == 1
    kopya = sqlite3.connect(dosyalar[0]); assert kopya.execute("SELECT x FROM t").fetchone() == (1,); kopya.close()
    kayit = s.query(SchedulerRun).filter(SchedulerRun.job_name == "sqlite_backup").order_by(SchedulerRun.id.desc()).first()
    assert kayit is not None and kayit.ok is True and kayit.finished_at is not None
    # detail maskeden geçer (BUG #258: uzun sayı dizileri `<uzun-sayi>` olur) — dosya adı damgası da maskelenir
    assert (kayit.detail or "").startswith("yedek: ") and ".db (" in kayit.detail and "silinen eski: 0" in kayit.detail


def test_cekirdek_tek_kaynak_ve_cli_ona_bagli():
    cli = (KOK / "scripts" / "backup.py").read_text(encoding="utf-8")
    assert "from app.yedek import" in cli
    assert "src_conn.backup(" not in cli, "CLI kendi kopyasını taşıyor"
    app_src = "".join(p.read_text(encoding="utf-8") for p in (KOK / "app").glob("*.py"))
    assert "from scripts" not in app_src and "import scripts" not in app_src


def test_bozuk_kaynak_hata_yukseltir_yarim_kopya_kalmaz(tmp_path):
    bozuk = tmp_path / "bozuk.db"
    bozuk.write_bytes(b"bu bir sqlite dosyasi degil" * 100)
    with pytest.raises(yedek.YedekHatasi):
        yedek.sqlite_yedekle(bozuk, tmp_path / "b", 30)
    assert not list((tmp_path / "b").glob("*.db"))
    with pytest.raises(yedek.YedekHatasi):
        yedek.sqlite_yedekle(tmp_path / "yok.db", tmp_path / "b", 30)
    with pytest.raises(yedek.YedekHatasi):
        yedek.sqlite_db_yolu("postgresql://x")
