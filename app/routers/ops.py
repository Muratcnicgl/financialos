"""
Operasyon görünürlüğü (P5.3 / BUG #203) — "cron çalıştı mı?" sorusunun cevabı.

Zamanlanmış işler yalnızca log dosyasına yazıyordu. Operatör, fiyat cron'unun gece
çalışıp çalışmadığını ancak konteyner log'unu okuyarak anlayabiliyordu; bir iş sessizce
ölürse (scheduler servisi ayakta ama job patlıyor) HAFTALARCA fark edilmezdi — fiyatlar
bayatlar, gece batch'i insight üretmez, kullanıcı bunu bilmez.

Kimlik gerektirir (iş adları/hata tipleri operasyon bilgisidir, herkese açılmaz).
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


class SchedulerDurumu(BaseModel):
    isler: list[IsDurumu]
    hic_calisma_yok: bool


@router.get("/scheduler", response_model=SchedulerDurumu)
def scheduler_durumu(db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)) -> SchedulerDurumu:
    """Her zamanlanmış işin son çalışma bilgisi (canlı kapı + operatör paneli için)."""
    adlar = [r[0] for r in db.query(SchedulerRun.job_name).distinct().all()]
    simdi = datetime.utcnow()
    isler: list[IsDurumu] = []
    for ad in adlar:
        son = (db.query(SchedulerRun)
               .filter(SchedulerRun.job_name == ad)
               .order_by(SchedulerRun.id.desc()).first())
        son_ok = (db.query(func.max(SchedulerRun.finished_at))
                  .filter(SchedulerRun.job_name == ad, SchedulerRun.ok.is_(True))
                  .scalar())
        isler.append(IsDurumu(
            job_name=ad,
            son_calisma=son.started_at if son else None,
            son_basarili=son_ok,
            son_sonuc=son.ok if son else None,
            detay=son.detail if son else None,
            saat_once=(round((simdi - son.started_at).total_seconds() / 3600, 1)
                       if son else None),
        ))
    return SchedulerDurumu(isler=isler, hic_calisma_yok=not isler)
