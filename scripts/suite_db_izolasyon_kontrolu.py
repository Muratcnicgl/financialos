"""
SÜİT ↔ CANLI DB İZOLASYON KONTROLÜ — "testler verime dokunuyor mu?" sorusunun ÖLÇÜLMÜŞ cevabı.

Neden var: canlı veritabanının `error_logs` tablosunda test kalıntıları bulundu
(`/api/_test_hata/patla`, `_fake_send() takes 2 positional...`). Bunlar tarihsel — BUG #078
(conftest'in canlı engine kullanması) ve BUG #235 (üretim `app` nesnesine kalıcı test ucu)
ile kapanan defektlerden kalma. Ama "artık dokunmuyor" bir İDDİA'dır; bu script onu ÖLÇER
(KURAL R3: koşan komut > kod > doküman).

Yöntem: canlı DB'nin bir KOPYASI alınır, süit `DATABASE_URL` o kopyayı gösterecek şekilde
koşturulur, öncesi/sonrası tüm tabloların satır sayıları karşılaştırılır. Tek satır bile
değişirse süit bir yerde gerçek veritabanına yazıyordur.

Kullanım (canlı veriye DOKUNMAZ — yalnız kopya üzerinde çalışır):
    .\\venv\\Scripts\\python.exe -m scripts.suite_db_izolasyon_kontrolu
    .\\venv\\Scripts\\python.exe -m scripts.suite_db_izolasyon_kontrolu --db data/financialos.db

Çıkış kodu: 0 temiz · 1 sızıntı var (hangi tabloda kaç satır değiştiği yazılır).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _satir_sayilari(db_yolu: str) -> dict[str, int]:
    c = sqlite3.connect(db_yolu)
    sayilar: dict[str, int] = {}
    try:
        for (tablo,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            try:
                sayilar[tablo] = c.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0]
            except sqlite3.Error:
                pass        # sanal/sistem tablosu
    finally:
        c.close()
    return sayilar


def main() -> int:
    ap = argparse.ArgumentParser(description="Süit canlı DB'ye yazıyor mu — ölç.")
    ap.add_argument("--db", default=str(KOK / "data" / "financialos.db"),
                    help="Referans (canlı) SQLite dosyası — yalnız KOPYALANIR")
    args = ap.parse_args()

    kaynak = Path(args.db)
    if not kaynak.exists():
        print(f"HATA: {kaynak} yok. --db ile yol ver.")
        return 2

    with tempfile.TemporaryDirectory() as gecici:
        kopya = Path(gecici) / "izolasyon_kontrolu.db"
        shutil.copy(kaynak, kopya)
        once = _satir_sayilari(str(kopya))
        print(f"Kopya hazir: {len(once)} tablo, {sum(once.values())} satir. Suit kosuyor...")

        # BUG #289: conftest artık `DATABASE_URL`'i süit-özel geçici dosyaya sabitliyor.
        # Bu araç sızıntıyı ÖLÇMEK için o sabiti bilerek devre dışı bırakır — aksi hâlde
        # ölçüm kendi korumasını ölçer ve her zaman "temiz" der (sahte yeşil).
        env = dict(os.environ, DATABASE_URL=f"sqlite:///{kopya.as_posix()}",
                   FINANCIALOS_SUITE_DB_OVERRIDE="1")
        sonuc = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q", "--no-header"],
                               cwd=KOK, env=env, capture_output=True, text=True)
        ozet = (sonuc.stdout.strip().splitlines() or ["(cikti yok)"])[-1]
        print("Suit:", ozet[:120])

        sonra = _satir_sayilari(str(kopya))
        fark = {t: (once.get(t, 0), sonra.get(t, 0))
                for t in set(once) | set(sonra) if once.get(t, 0) != sonra.get(t, 0)}

    if fark:
        print("\nSIZINTI VAR — suit gercek veritabanina yazdi:")
        for tablo, (a, b) in sorted(fark.items()):
            print(f"  {tablo}: {a} -> {b}")
        print("\nBu, BUG #078/#235 sinifidir: testin yazdigi satir canli veriye karisir.")
        return 1

    print("\nTEMIZ: suit, DATABASE_URL ile gosterilen veritabanina hicbir satir yazmadi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
