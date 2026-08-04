"""
P5 (Wave-9) — H14: YEDEKTEN GERİ YÜKLEME PROVASI.

"Yedek almak" bir güvence değildir; **geri yüklenebildiği kanıtlanmamış yedek yoktur.**
Depoda `scripts/backup.py` vardı ama geri yükleme yolu hiç yazılmamış ve hiç denenmemişti
(felaket anında ilk kez denemek en kötü senaryo).

Bu dosya gerçek bir tatbikat koşar:
  veri yaz → yedek al → **veriyi yok et** → geri yükle → veri birebir aynı mı?

Ayrıca yıkıcı script'in emniyet kilitleri (onaysız yazmama, bozuk yedeği reddetme,
geri yüklemeden önce mevcut DB'nin kopyasını alma) doğrulanır.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts import restore as restore_mod


def _db_yarat(yol: Path, kayitlar: list[tuple[int, str, float]]) -> None:
    con = sqlite3.connect(yol)
    try:
        con.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, balance REAL)")
        con.execute("CREATE TABLE alembic_version (version_num TEXT)")
        con.execute("INSERT INTO alembic_version VALUES ('c3d4e5f6a7b8')")
        con.executemany("INSERT INTO accounts VALUES (?,?,?)", kayitlar)
        con.commit()
    finally:
        con.close()


def _oku(yol: Path) -> list[tuple]:
    con = sqlite3.connect(yol)
    try:
        return con.execute("SELECT id, name, balance FROM accounts ORDER BY id").fetchall()
    finally:
        con.close()


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    """İzole DB + yedek dizini (gerçek veriye ASLA dokunulmaz)."""
    veri = tmp_path / "financialos.db"
    yedek_dir = tmp_path / "backups"
    yedek_dir.mkdir()
    monkeypatch.setattr(restore_mod, "BACKUP_DIR", yedek_dir)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{veri.as_posix()}")
    return veri, yedek_dir


def test_geri_yukleme_provasi_veriyi_aynen_getirir(ortam):
    """H14 çekirdek kanıtı: yok edilen veri yedekten BİREBİR geri gelir."""
    veri, yedek_dir = ortam
    orijinal = [(1, "Maaş Hesabım", 12345.67), (2, "Kredi Kartım", -4200.0)]
    _db_yarat(veri, orijinal)

    # Yedek al (backup.py'nin kullandığı SQLite online backup API'si ile aynı yol)
    yedek = yedek_dir / "prova.db"
    kaynak = sqlite3.connect(veri)
    hedef = sqlite3.connect(yedek)
    try:
        kaynak.backup(hedef)
    finally:
        hedef.close()
        kaynak.close()

    # FELAKET: canlı veri yok edilir
    veri.unlink()
    assert not veri.exists()

    rc = restore_mod.restore(yedek, veri, dry_run=False)
    assert rc == 0, "Geri yükleme başarısız"
    assert veri.exists(), "Geri yükleme sonrası DB yok"
    assert _oku(veri) == orijinal, "Geri yüklenen veri orijinalden FARKLI"


def test_onay_olmadan_hicbir_sey_yazilmaz(ortam):
    """Yıkıcı işlem varsayılan olarak DENEME modunda (BUG #164 dersi)."""
    veri, yedek_dir = ortam
    _db_yarat(veri, [(1, "Canlı veri", 100.0)])
    yedek = yedek_dir / "baska.db"
    _db_yarat(yedek, [(9, "Yedekteki veri", 999.0)])

    rc = restore_mod.restore(yedek, veri, dry_run=True)
    assert rc == 0
    assert _oku(veri) == [(1, "Canlı veri", 100.0)], "DRY-RUN canlı veriyi değiştirdi!"


def test_bozuk_yedek_canliyi_ezmez(ortam):
    """Bozuk/boş yedek kabul edilirse felaketi ikiye katlar."""
    veri, yedek_dir = ortam
    _db_yarat(veri, [(1, "Canlı veri", 100.0)])
    bozuk = yedek_dir / "bozuk.db"
    bozuk.write_bytes(b"bu bir sqlite dosyasi degil" * 10)

    rc = restore_mod.restore(bozuk, veri, dry_run=False)
    assert rc == 2, "Bozuk yedek reddedilmedi"
    assert _oku(veri) == [(1, "Canlı veri", 100.0)], "Bozuk yedek canlı veriyi EZDİ"


def test_bos_yedek_reddedilir(ortam):
    veri, yedek_dir = ortam
    _db_yarat(veri, [(1, "Canlı", 1.0)])
    bos = yedek_dir / "bos.db"
    bos.write_bytes(b"")
    assert restore_mod.restore(bos, veri, dry_run=False) == 2


def test_geri_yuklemeden_once_emniyet_kopyasi_alinir(ortam):
    """Yanlış yedeği yüklersen geri dönebilmelisin."""
    veri, yedek_dir = ortam
    _db_yarat(veri, [(1, "Eski canlı", 5.0)])
    yedek = yedek_dir / "yeni.db"
    _db_yarat(yedek, [(2, "Yedekten", 7.0)])

    assert restore_mod.restore(yedek, veri, dry_run=False) == 0
    emniyet = list(veri.parent.glob("*pre-restore*.db"))
    assert emniyet, "Geri yüklemeden önce mevcut DB'nin kopyası alınmadı"
    assert _oku(emniyet[0]) == [(1, "Eski canlı", 5.0)]


def test_yedek_dogrulama_alembic_surumunu_raporlar(ortam):
    """Yedek eski şemadaysa fark edilmeli (sessiz uyumsuzluk = gizli felaket)."""
    _, yedek_dir = ortam
    yedek = yedek_dir / "surum.db"
    _db_yarat(yedek, [(1, "x", 1.0)])
    ok, mesaj = restore_mod.dogrula(yedek)
    assert ok and "c3d4e5f6a7b8" in mesaj, f"Sürüm raporlanmadı: {mesaj}"


def test_postgres_kurulumunda_dosya_kopyalamaz(monkeypatch, capsys):
    """Prod Postgres'te yanlış araçla veri kaybını önle — doğru komutu yazdır."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/financialos")
    rc = restore_mod.main(["--from", "olmayan.db", "--confirm"])
    cikti = capsys.readouterr().out
    assert rc == 3
    assert "psql" in cikti and "runbook" in cikti
