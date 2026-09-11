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

import math
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.rate_limit import rate_limit
from app.models import User, SchedulerRun, ApiCallLog, ApiCallStatus
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


# ── LLM SAĞLAYICI SAĞLIĞI (BUG #404 · OBS-007 + OBS-016) ─────────────────────────
# Veri `api_call_log`'da zaten vardı (sağlayıcı, durum, süre); bakan yüzey yoktu (L61).
# Süre BUG #404'e kadar yalnız ilk halkada ölçülüyordu — 311 satırın 279'u "0 ms"ydi;
# artık her istek kendi süresini taşır, bilinmeyen NULL'dur ve yüzdeliklere GİRMEZ.

class SaglayiciSagligi(BaseModel):
    provider: str
    cagri: int
    basarili: int
    basarisiz: int
    hiz_sinirli: int
    basari_orani: Optional[float] = None    # cagri 0 ise None (bilinmeyen sıfır değil)
    olculen_sure: int                       # süresi bilinen istek sayısı
    p50_ms: Optional[int] = None
    p95_ms: Optional[int] = None
    p99_ms: Optional[int] = None


class LlmSagligi(BaseModel):
    gun: int
    saglayicilar: list[SaglayiciSagligi]


def yuzdelik(degerler: list[int], p: float) -> Optional[int]:
    """En yakın-sıra yüzdeliği (nearest-rank). Boş listede None."""
    if not degerler:
        return None
    sirali = sorted(degerler)
    k = max(1, math.ceil(p / 100 * len(sirali)))
    return int(sirali[min(k, len(sirali)) - 1])


def saglayici_sagligi(db: Session, gun: int = 7) -> list[SaglayiciSagligi]:
    esik = datetime.utcnow() - timedelta(days=gun)
    # scope-exempt: operatör toplamı — kullanıcılar ARASI sağlayıcı sağlığı ölçülür; yalnız
    # sağlayıcı/durum/süre okunur, satır içeriği ve kullanıcı kimliği dışarı çıkmaz.
    satirlar = (db.query(ApiCallLog.provider, ApiCallLog.status, ApiCallLog.duration_ms)  # scope-exempt: operatör toplamı, PII yok
                .filter(ApiCallLog.called_at >= esik).all())
    kova: dict[str, dict] = {}
    for provider, status, sure in satirlar:
        k = kova.setdefault(provider, {"cagri": 0, "basarili": 0, "basarisiz": 0, "hiz_sinirli": 0, "sureler": []})
        k["cagri"] += 1
        if status == ApiCallStatus.success:
            k["basarili"] += 1
        elif status == ApiCallStatus.rate_limited:
            k["hiz_sinirli"] += 1
        else:
            k["basarisiz"] += 1
        if sure is not None:
            k["sureler"].append(int(sure))
    cikti = []
    for provider in sorted(kova):
        k = kova[provider]
        cikti.append(SaglayiciSagligi(
            provider=provider, cagri=k["cagri"], basarili=k["basarili"], basarisiz=k["basarisiz"],
            hiz_sinirli=k["hiz_sinirli"],
            basari_orani=round(k["basarili"] / k["cagri"], 3) if k["cagri"] else None,
            olculen_sure=len(k["sureler"]),
            p50_ms=yuzdelik(k["sureler"], 50), p95_ms=yuzdelik(k["sureler"], 95), p99_ms=yuzdelik(k["sureler"], 99),
        ))
    return cikti


@router.get("/llm", response_model=LlmSagligi)
def llm_sagligi(gun: int = 7, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> LlmSagligi:
    """Son N günde sağlayıcı başına çağrı/başarı/hız-sınırı sayıları ve gecikme yüzdelikleri."""
    gun = max(1, min(gun, 90))
    return LlmSagligi(gun=gun, saglayicilar=saglayici_sagligi(db, gun))


# ── İSTEMCİ HATA RAPORU (BUG #406 · OBS-013) ─────────────────────────────────────
# Tarayıcıda çöken panel ve yakalanmamış promise reddi artık sunucu defterine düşer;
# `error_logs` aynı parmak-izi birleştirmesiyle "kaç kez, kimde, hangi yolda" der.
# Kimlik zorunlu (anonim çöp yok) ve IP başına 30/dk (döngüye giren sekme defteri dolduramaz).

class IstemciHatasi(BaseModel):
    tip: str = Field(default="Error", max_length=60)
    mesaj: str = Field(default="", max_length=500)
    yigin: str = Field(default="", max_length=4000)
    yol: str = Field(default="", max_length=120)     # aktif sekme / konum — PII değil


class IstemciHatasiCevap(BaseModel):
    kayit_id: Optional[int] = None


@router.post("/istemci-hata", response_model=IstemciHatasiCevap, status_code=202)
def istemci_hatasi_bildir(govde: IstemciHatasi, request: Request,
                          db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)) -> IstemciHatasiCevap:
    """Tarayıcı hatasını (çöken panel, yakalanmamış promise) sunucu hata defterine yazar."""
    rate_limit(request, "istemci_hata", db)
    from app.correlation import istek_id
    from app.error_tracking import kaydet_istemci
    kid = kaydet_istemci(db, tip=govde.tip, mesaj=govde.mesaj, yol=govde.yol, yigin=govde.yigin,
                         user_id=user.id, istek_id=istek_id())
    return IstemciHatasiCevap(kayit_id=kid)
