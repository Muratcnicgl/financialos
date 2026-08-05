"""
Genel (kimliksiz) ürün bilgisi + DESTEK KANALI (P8 / BUG #210).

Sorun: destek adresi YALNIZCA e-posta şablonlarının içinde yaşıyordu. Yani kullanıcı
ancak şifre sıfırlama e-postası alabilirse destekten haberdar oluyordu. **Giriş
yapamayan** bir beta kullanıcısının (yanlış şifre, doğrulanmamış e-posta, kilitli hesap,
davet kodu çalışmıyor) ulaşabileceği HİÇBİR kanal yoktu — kullanıcı rehberi bile
"davet kodunu ileten kişiye yaz" diyordu; ürünün kendisi sessizdi. Açık betada (P8)
bu doğrudan kullanıcı kaybıdır ve KVKK'nın "veri sorumlusuna başvuru" hakkını da
fiilen kullanılamaz kılar.

Bu router giriş ekranının okuyabileceği kimliksiz bir uç sağlar:
  - destek adresi (env `SUPPORT_EMAIL`, kişisel adres GÖMÜLÜ DEĞİL — BUG #205)
  - sürüm (hata bildiriminde "hangi kod koşuyordu" — BUG #200)
  - kayıt modu (giriş ekranı davet kodunun ZORUNLU olduğunu söyleyebilsin)
  - hukuki metin bağlantıları (KVKK/şartlar — kayıt öncesi okunabilmeli)
  - `durum`: servis ayakta mı + veritabanı yanıt veriyor mu

GİZLİLİK/GÜVENLİK: burada operasyon ayrıntısı YOK. İş adları, hata tipleri, cron
zamanları `/api/ops/*` altında kalır (kimlik ister). Buradan yalnız kullanıcının
kararını etkileyen bilgi yayılır.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.beta_access import registration_mode
from app.dependencies import get_db
from app.routers.legal import BELGELER as LEGAL_BELGELER
from app.services.email import destek_adresi
from app.version import APP_VERSION, build_commit

router = APIRouter(prefix="/api/meta", tags=["meta"])


class UrunBilgisi(BaseModel):
    urun: str
    surum: str
    build: str
    destek: str
    kayit_modu: str          # "invite_only" | "open" | "closed"
    davet_kodu_gerekli: bool
    hukuki: dict[str, str]


class Durum(BaseModel):
    saglikli: bool
    api: bool
    veritabani: bool


@router.get("", response_model=UrunBilgisi)
def urun_bilgisi() -> UrunBilgisi:
    """Giriş ekranının (kimliksiz) okuduğu ürün künyesi."""
    mod = registration_mode()
    return UrunBilgisi(
        urun="FinancialOS",
        surum=APP_VERSION,
        build=build_commit(),
        destek=destek_adresi(),
        kayit_modu=mod,
        davet_kodu_gerekli=(mod == "invite_only"),
        # Slug'lar legal router'ın BELGELER sözlüğünden türetilir — elle yazılan bir
        # kopya zamanla kayar ve giriş ekranı 404'e link verir (testle kilitli).
        hukuki={slug: f"/api/legal/{slug}" for slug in LEGAL_BELGELER},
    )


@router.get("/durum", response_model=Durum)
def durum(db: Session = Depends(get_db)) -> Durum:
    """Kimliksiz servis durumu — "bende mi, sizde mi?" sorusunun cevabı.

    Kullanıcı hata gördüğünde önce buraya bakabilir. Ayrıntı VERİLMEZ (hangi tablo,
    hangi hata) — bu bilgi saldırgana yarar; kullanıcıya yaramaz.
    """
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 — durum ucu asla patlamamalı, "sağlıksız" demeli
        db_ok = False
    return Durum(saglikli=db_ok, api=True, veritabani=db_ok)
