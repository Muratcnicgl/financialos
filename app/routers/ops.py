"""
Operasyon görünürlüğü (P5.3 / BUG #203) — "cron çalıştı mı?" sorusunun cevabı.

Zamanlanmış işler yalnızca log dosyasına yazıyordu. Operatör, fiyat cron'unun gece
çalışıp çalışmadığını ancak konteyner log'unu okuyarak anlayabiliyordu; bir iş sessizce
ölürse (scheduler servisi ayakta ama job patlıyor) HAFTALARCA fark edilmezdi — fiyatlar
bayatlar, gece batch'i insight üretmez, kullanıcı bunu bilmez.

Kimlik gerektirir (iş adları/hata tipleri operasyon bilgisidir, herkese açılmaz).

GUNCELLEMELER
-------------
BUG #240 fix (D24): iş adları `SchedulerRun` tablosundan türetiliyordu — yani HİÇ
çalışmamış (ör. ilk günden beri patlayan) bir iş uçta HİÇ görünmüyordu; boş liste
"her şey yolunda" gibi okunuyordu. Adlar artık `app.scheduler.PLANLI_ISLER`'den
gelir: planlı ama koşmamış iş `hic_calismadi`, bayat kalmış iş `gecikti` ile işaretlenir.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import User, SchedulerRun
from app.serializers import UtcDateTime

router = APIRouter(prefix="/api/ops", tags=["ops"])


class IsDurumu(BaseModel):
    job_name: str
    son_calisma: Optional[UtcDateTime] = None
    son_basarili: Optional[UtcDateTime] = None
    son_sonuc: Optional[bool] = None
    detay: Optional[str] = None
    saat_once: Optional[float] = None
    planli: bool = True          # BUG #240: PLANLI_ISLER'de mi, yoksa yalnız tarihsel kayıt mı
    hic_calismadi: bool = False  # BUG #240: planlı ama bir kez bile koşmamış
    gecikti: bool = False        # BUG #240: son koşum beklenen periyodun 1.5 katından eski


class SchedulerDurumu(BaseModel):
    isler: list[IsDurumu]
    hic_calisma_yok: bool
    sorunlu_isler: list[str] = []   # BUG #240: hiç koşmayan + geciken + son koşumu hatalı


# Gecikme eşiği: beklenen periyodun 1.5 katı. Tek gecikmiş koşum (misfire_grace_time
# 3600 sn) alarm üretmesin, iki periyot kaçırmak ise sessiz kalmasın.
GECIKME_KATSAYISI = 1.5


@router.get("/scheduler", response_model=SchedulerDurumu)
def scheduler_durumu(db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)) -> SchedulerDurumu:
    """Her zamanlanmış işin son çalışma bilgisi (canlı kapı + operatör paneli için)."""
    from app.scheduler import PLANLI_ISLER, DIS_PLANLI_ISLER   # BUG #240: iş adlarının tek kaynağı

    periyotlar = {p.ad: p.beklenen_periyot_saat
                  for p in (*PLANLI_ISLER, *DIS_PLANLI_ISLER)}   # dış iş = yedek (compose)
    kayitli = [r[0] for r in db.query(SchedulerRun.job_name).distinct().all()]
    # Planlı işler önce (koşmamış olsa da görünür), sonra tarihsel/bilinmeyen adlar.
    adlar = list(periyotlar) + [a for a in sorted(kayitli) if a not in periyotlar]
    simdi = datetime.utcnow()
    isler: list[IsDurumu] = []
    for ad in adlar:
        son = (db.query(SchedulerRun)
               .filter(SchedulerRun.job_name == ad)
               .order_by(SchedulerRun.id.desc()).first())
        son_ok = (db.query(func.max(SchedulerRun.finished_at))
                  .filter(SchedulerRun.job_name == ad, SchedulerRun.ok.is_(True))
                  .scalar())
        saat_once = (round((simdi - son.started_at).total_seconds() / 3600, 1)
                     if son else None)
        periyot = periyotlar.get(ad)
        isler.append(IsDurumu(
            job_name=ad,
            son_calisma=son.started_at if son else None,
            son_basarili=son_ok,
            son_sonuc=son.ok if son else None,
            detay=son.detail if son else None,
            saat_once=saat_once,
            planli=ad in periyotlar,
            hic_calismadi=(son is None and ad in periyotlar),
            gecikti=bool(periyot and saat_once is not None
                         and saat_once > periyot * GECIKME_KATSAYISI),
        ))
    sorunlu = [i.job_name for i in isler
               if i.hic_calismadi or i.gecikti or i.son_sonuc is False]
    return SchedulerDurumu(isler=isler,
                           hic_calisma_yok=not kayitli,
                           sorunlu_isler=sorunlu)
