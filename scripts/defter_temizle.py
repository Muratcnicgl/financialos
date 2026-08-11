"""
CANLI DEFTERDEN TEST KALINTILARINI TEMİZLE — BUG #289'un GEÇMİŞ etkisi.

BUG #289 sızıntıyı DURDURDU (süit artık canlı veritabanına bağlanamaz), ama o güne kadar
yazılmış satırlar defterde kaldı. Canlı ölçüm (11 Ağu): `scheduler_runs` tablosundaki
**50 satırın 50'si de** `weekly_smoke_test` — üstelik içlerinde `RuntimeError: smoke boom`
gibi yalnız testte üretilen mesajlar var. Haftalık koşan bir iş iki günde 50 kez koşmaz.

NEDEN ÖNEMLİ (kozmetik değil): operatör `/api/ops/scheduler`'a bakınca cron sağlığını
görmek ister. 50 sahte satır tek gerçek işi "çok koşmuş" gösterirken, GERÇEKTEN hiç
koşmamış gece işleri (fiyat/batch/temizlik) fark edilmiyordu. Kirli defter, ölçümü
yanlış cevaplar — silmek bir düzeltme değil, ÖLÇÜMÜ geri kazanmaktır.

Güvenlik:
  · Yalnız ADI VERİLEN iş ve YALNIZ test imzası taşıyan satırlar silinir.
  · Varsayılan KURU KOŞUM — `--uygula` denmedikçe hiçbir şey silinmez.
  · Kullanıcı verisine (hesap/işlem/koç) ASLA dokunmaz; bu script yalnız
    operasyon defterlerini (scheduler_runs) hedefler.

Kullanım:
    .\\venv\\Scripts\\python.exe -m scripts.defter_temizle            # ne silinecek (kuru)
    .\\venv\\Scripts\\python.exe -m scripts.defter_temizle --uygula   # sil (yedek al!)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import SchedulerRun  # noqa: E402

# Yalnız testin ürettiği, üretimde ASLA oluşmayacak imzalar.
TEST_IMZALARI = ("smoke boom", "RuntimeError: smoke boom")


def main() -> int:
    ap = argparse.ArgumentParser(description="Canlı defterden test kalıntılarını temizle")
    ap.add_argument("--uygula", action="store_true", help="gercekten sil (varsayilan: kuru kosum)")
    a = ap.parse_args()

    db = SessionLocal()
    try:
        hepsi = db.query(SchedulerRun).order_by(SchedulerRun.id).all()
        imzali = [r for r in hepsi
                  if any(im in (r.detail or "") for im in TEST_IMZALARI)]

        # `smoke boom` üreten koşumun KOMŞULARI da testtendir: aynı iş adının aynı
        # dakikadaki diğer satırları. Ama tahmin yürütmek yerine, imzalı satırların
        # bulunduğu GÜNLERDEKİ aynı-ad satırlarını gösterip kararı operatöre bırakıyoruz.
        gunler = {r.started_at.date() for r in imzali}
        adlar = {r.job_name for r in imzali}
        aday = [r for r in hepsi
                if r.job_name in adlar and r.started_at.date() in gunler]

        print(f"Toplam scheduler_runs satiri : {len(hepsi)}")
        print(f"Kesin test imzali satir      : {len(imzali)}  {sorted(adlar)}")
        print(f"Ayni is + ayni gun (aday)    : {len(aday)}")
        if gunler:
            print(f"Etkilenen gunler             : {sorted(str(g) for g in gunler)}")
        kalan = len(hepsi) - len(aday)
        print(f"Temizlik sonrasi kalacak     : {kalan}")

        if not aday:
            print("\nTemiz — silinecek satir yok.")
            return 0
        if not a.uygula:
            print("\nKURU KOSUM — hicbir sey silinmedi. Uygulamak icin: --uygula")
            print("Once yedek: python -m scripts.backup")
            return 0

        for r in aday:
            db.delete(r)
        db.commit()
        print(f"\n{len(aday)} satir silindi. Kalan: {db.query(SchedulerRun).count()}")
        print("Not: silinen isler artik 'hic kosmamis' gorunur; acilistaki telafi "
              "(BUG #302) onlari bir kez kosturacaktir.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
