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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.beta_access import registration_mode
from app.dependencies import get_db
from app.routers.legal import BELGELER as LEGAL_BELGELER
from app.services.email import destek_adresi
from app.version import APP_VERSION, build_commit

router = APIRouter(prefix="/api/meta", tags=["meta"])

# BUG #247 (D39): HAZIR OLMA ucu ayrı bir yolda (`/api/ready`) — HEALTHCHECK, deploy
# rollback kapısı ve canlı kapı bunu okur. Prefix'siz router, `app/main.py`'de kaydedilir.
hazir_router = APIRouter(tags=["health"])


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


# ============================================================
# HAZIR OLMA (BUG #247 / D39)
# ============================================================
#
# `/api/health` CANLILIK ölçer: süreç ayakta mı (bağımlılık yok, her zaman 200). Ona
# bakan bir rollback kapısı, DB çökmüşken ya da migration koşulmamışken de YEŞİL kalır —
# konteyner "healthy" görünür, otomatik rollback tetiklenmez, operatör paneli yeşildir ve
# kullanıcı bu sırada her ekranda 500 alır. HAZIR OLMA ayrı ölçülür ve başarısızlıkta
# **503** döner (200 gövdesindeki `saglikli: false` hiçbir orkestratörü tetiklemez).


def sema_durumu(db: Session) -> tuple[str, str | None]:
    """(durum, beklenen_head): 'guncel' | 'uyumsuz' | 'atlandi' (test/create_all yolu)."""
    from app.schema_guard import _kod_head, _db_surumu
    beklenen = _kod_head()
    if beklenen is None:
        return "atlandi", None
    try:
        mevcut = _db_surumu(db.get_bind())
    except Exception:  # noqa: BLE001
        return "atlandi", beklenen
    if mevcut is None:
        return "atlandi", beklenen
    return ("guncel" if mevcut == beklenen else "uyumsuz"), beklenen


@hazir_router.get("/api/ready", tags=["health"])
def hazir(db: Session = Depends(get_db)) -> dict:
    """Trafik almaya HAZIR mıyız: DB yanıt veriyor + şema kodla aynı sürümde mi.

    Sorun varsa 503 — Docker HEALTHCHECK, `scripts/deploy.sh` rollback kapısı ve
    `scripts/live_gate.py` bu ucu okur.
    """
    sorunlar: list[dict] = []

    # BUG #263 (P5.5): havuz DOLUYKEN `SELECT 1` denemek bu ucu `pool_timeout` kadar
    # (varsayılan 30 sn) ASAR. Docker HEALTHCHECK o kadar beklemez → konteyner sağlıksız
    # işaretlenir ve yeniden başlar; yani geçici bir yük dalgası KALICI kesintiye döner.
    # Doygunluk bağlantı İSTEMEDEN ölçülür → hızlı ve dürüst 503.
    from app.capacity import havuz_doygun_mu
    if havuz_doygun_mu():
        govde = {"hazir": False, "db": "havuz_dolu", "sema": "atlandi", "surum": APP_VERSION,
                 "sorunlar": [{"ad": "db", "detay": "baglanti havuzu doygun"}]}
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=govde)

    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001 — ayrıntı sızdırmadan sorunu bildir
        db_ok = False
        sorunlar.append({"ad": "db", "detay": type(e).__name__})

    sema, beklenen = ("atlandi", None)
    if db_ok:
        sema, beklenen = sema_durumu(db)
        if sema == "uyumsuz":
            sorunlar.append({"ad": "sema", "detay": f"migration koşulmamış (kod={beklenen})"})

    govde = {
        "hazir": not sorunlar,
        "db": "ok" if db_ok else "erisilemiyor",
        "sema": sema,
        "surum": APP_VERSION,
    }
    if sorunlar:
        govde["sorunlar"] = sorunlar
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=govde)
    return govde
