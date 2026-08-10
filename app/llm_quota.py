"""
ADR-041 / BUG #188 — kullanıcı başına LLM kotası. **Tek kaynak (BUG #228 / D07+D16).**

Kota muhasebesi tarihsel olarak `app/routers/coach.py` içinde yaşıyordu ve yalnız
`POST /api/coach/chat` yolunda dayatılıyordu. LLM üreten DİĞER yollar (premortem ucu,
aksiyon onayının arka plan yansıması) tavanı sıfırlıyordu: kotası dolmuş bir kullanıcı
bile premortem'i döngüde çağırarak sınırsız üretim yaptırabiliyor, üstelik bu trafik
`ApiCallLog`'a hiç yazılmadığı için maliyet/hata metriklerinde GÖRÜNMÜYORDU (operatör
patlamayı ölçtükten sonra bile nedenini bulamaz).

Bu modül uca değil **LLM kullanımına** bağlıdır; yeni bir LLM yolu eklendiğinde buradan
geçmesi gerekir (`tests/test_llm_kota_kapisi.py` bunu statik olarak dayatır).

Rezervasyon deseni (BUG #212 / H17): satır çağrı ÖNCESİ yazılır, sonra "benden önce/benimle
birlikte kaç satır var" (id sırası) sayılır. Sıra tavanı aşıyorsa rezervasyon geri alınır.
"Oku → çağır → yaz" düzeninde eşzamanlı N istek aynı eski sayıyı okuyup hepsi geçiyordu.

BUG #234 (D14+D15): sayacın BİRİMİ düzeltildi.
- **D15 — birim ÇAĞRI'dır, mesaj değil.** Bir koç mesajı iki-geçiş mimarisi (plan + ana
  cevap), retry dalları ve fallback zinciri yüzünden 1-4 GERÇEK sağlayıcı isteği üretir;
  muhasebeye tek satır yazılıyordu → ADR-041'in ilan ettiği "80 çağrı ~40 mesaj" tavanı
  gerçeğin 2-3 katı harcamaya izin veriyordu. Artık gerçek istekler `cagri_olcumu()`
  kapsamında sayılır (kanca `app/coach.py`'de sağlayıcıların `_raw_chat`'ine otomatik
  takılır) ve istek sonunda `ek_cagrilari_uzlastir` ile sayaca yansıtılır.
- **D14 — paylaşılan sağlayıcı kotası kullanıcı-başına sayılıyordu** → `paylasilan_cagri_sayisi`
  kullanıcı filtresizdir (sağlayıcı kotası fatura gibi tek havuzdur).

Uzlaştırma çağrı SONRASI olur (gerçek sayı ancak o zaman bilinir): tavan en fazla bir
mesaj kadar aşılabilir, bir sonraki istek rezervasyonda 429 alır. Eşzamanlılık koruması
(rezervasyon) bozulmadığı için bu bilinçli ve sınırlı bir gecikmedir.

BUG #274 (LLM-006): ölçüm artık SAYMAKLA kalmıyor, isteğin KİMLİĞİNİ de taşıyor.
Kanca `_raw_chat`'i sarmaladığı için ağa çıkan her isteğin sağlayıcısını, çalışan modelini
ve sağlayıcının döndürdüğü token'larını tek noktada görür — ama bunları atıp yalnız "+1"
yazıyordu. Artık her gerçek istek bir KAYIT üretir ve defterdeki satır o kayıttan doldurulur
(sağlayıcı + model + token + tahmini maliyet). Tek kaynak: `app/llm_cost.py`.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Iterator, List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import llm_cost
from app.models import ApiCallLog, ApiCallStatus
from app.error_tracking import temizle  # BUG #258: kalici hata metni maskeli yazilir

# Amaç etiketleri (BUG #274): `model` sütununa YAZILMAZ, kendi sütununda taşınır.
AMAC_KOC = "koc"
AMAC_PREMORTEM = "premortem"
AMAC_YANSIMA = "yansima"

logger = logging.getLogger(__name__)

KOTA_MESAJI = (
    "Bugunku koc kullanim hakkin doldu. Yarin yeniden sohbet edebilirsin — "
    "paneller ve hesaplamalar calismaya devam ediyor."
)


def _gun_baslangici() -> datetime:
    """BUG #133: sayaç UTC gününe göre — `called_at` ile aynı zaman ekseni."""
    return datetime.combine(datetime.utcnow().date(), datetime.min.time())


def kullanici_gunluk_tavan() -> int:
    """BUG #188 (P3): kullanıcı başına günlük LLM çağrı tavanı (0 = kapalı).

    Koç mesajı başına 2 çağrı yapılır (iki-geçiş mimarisi) → varsayılan 80 çağrı
    ~40 mesaj/gün. Çok-kullanıcıda hem MALİYET tavanı hem ADALET guard'ıdır:
    sağlayıcı kotası paylaşıldığı için bir kullanıcı herkesi kilitleyemez.
    """
    try:
        return max(0, int(os.getenv("COACH_DAILY_USER_LIMIT", "80")))
    except ValueError:
        return 80


def bugunku_cagri_sayisi(db: Session, user_id: int) -> int:
    """Kullanıcının bugünkü (UTC günü) TÜM sağlayıcılardaki çağrı sayısı."""
    return (
        db.query(func.count(ApiCallLog.id))
        .filter(ApiCallLog.user_id == user_id, ApiCallLog.called_at >= _gun_baslangici())
        .scalar()
    ) or 0


def paylasilan_cagri_sayisi(db: Session, provider: str) -> int:
    """BUG #234 (D14): bir sağlayıcının bugünkü TOPLAM çağrısı — kullanıcı filtresi YOK.

    Sağlayıcı günlük kotası (ör. Gemini ücretsiz kademe 1500/gün) tek bir havuzdur:
    anahtarı paylaşan herkes aynı sayacı tüketir. Bu sorgu kullanıcı-başına filtreliyken
    havuz hiç ölçülmüyordu; kişisel tavan (80) her zaman önce dolduğu için %80 uyarısı ve
    %100 blok dalı matematiksel olarak erişilemezdi.

    scope-exempt: kasten çapraz-kullanıcı — ölçülen şey kullanıcı verisi değil, paylaşılan
    dış kaynağın (API anahtarı) tüketimi. Kişi-bazlı hiçbir alan okunmaz/dönmez.
    """
    # scope-exempt: KASTEN çapraz-kullanıcı — ölçülen şey kullanıcı verisi değil, paylaşılan
    # dış kaynağın (API anahtarı/kota) tüketimi (BUG #234). Kişi-bazlı alan okunmaz/dönmez.
    return (
        db.query(func.count(ApiCallLog.id))
        .filter(ApiCallLog.provider == (provider or "?").lower(),
                ApiCallLog.called_at >= _gun_baslangici())
        .scalar()
    ) or 0


# ------------------------------------------------------------
# GERÇEK ÇAĞRI ÖLÇÜMÜ (BUG #234 / D15)
# ------------------------------------------------------------

@dataclass
class Cagri:
    """Ağa fiilen çıkan TEK bir sağlayıcı isteği — defterdeki bir satırın karşılığı.

    BUG #274: eskiden bu kaydın yerine yalnız bir sayaç vardı; sağlayıcının döndürdüğü
    usage ve çalışan model, ölçüm noktasından geçip atılıyordu.
    """

    saglayici: str
    model: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None

    def maliyet_usd(self) -> Optional[Decimal]:
        return llm_cost.maliyet_usd(self.saglayici, self.model, self.tokens_in, self.tokens_out)


_olcum: ContextVar[Optional[List[Cagri]]] = ContextVar("llm_cagri_olcumu", default=None)


@contextmanager
def cagri_olcumu() -> Iterator[List[Cagri]]:
    """Kapsam içinde ağa çıkan GERÇEK sağlayıcı isteklerini sırayla toplar.

    ContextVar kullanılır: iç içe/eşzamanlı isteklerin ölçümleri karışmaz (aynı süreçte
    çalışan başka bir kullanıcının çağrısı bu kullanıcının kotasına yazılmaz).
    """
    olcum: List[Cagri] = []
    token = _olcum.set(olcum)
    try:
        yield olcum
    finally:
        _olcum.reset(token)


def cagri_kaydet(provider: str, model: Optional[str] = None,
                 usage: Optional[Dict[str, Optional[int]]] = None) -> None:
    """Bir gerçek sağlayıcı isteğini ölçüme ekler (kapsam yoksa sessiz no-op).

    `usage` sağlayıcının döndürdüğü `{"input_tokens": .., "output_tokens": ..}` sözlüğüdür;
    dönmeyen sağlayıcıda (ör. yerel Ollama) None kalır — uydurulmaz.

    Kapsam dışı yollar (cron, script, testler) muhasebe kancası olmadan da çalışmalıdır —
    ölçüm eksikliği ürünü kilitleyemez (L6).
    """
    olcum = _olcum.get()
    if olcum is None:
        return
    u = usage or {}
    olcum.append(Cagri(
        saglayici=(provider or "?").lower(),
        model=model,
        tokens_in=u.get("input_tokens"),
        tokens_out=u.get("output_tokens"),
    ))


def sayim(olcum: List[Cagri]) -> Dict[str, int]:
    """Sağlayıcı bazında istek adedi (kota mantığının ihtiyaç duyduğu özet)."""
    ozet: Dict[str, int] = {}
    for c in olcum:
        ozet[c.saglayici] = ozet.get(c.saglayici, 0) + 1
    return ozet


def _satiri_doldur(satir: ApiCallLog, cagri: Cagri, amac: Optional[str]) -> None:
    """Defter satırına isteğin KİMLİĞİNİ yazar: sağlayıcı, model, token, tahmini maliyet."""
    satir.provider = cagri.saglayici
    if cagri.model:
        satir.model = cagri.model
    satir.tokens_in = cagri.tokens_in
    satir.tokens_out = cagri.tokens_out
    satir.est_cost_usd = cagri.maliyet_usd()
    if amac:
        satir.amac = amac


def ek_cagrilari_uzlastir(db: Session, user_id: int, olcum: List[Cagri],
                          rezervasyon: Optional[ApiCallLog] = None,
                          amac: str = AMAC_KOC) -> int:
    """Ölçülen gerçek istekleri defter satırlarıyla BİREBİR eşler (D15 + BUG #274).

    Rezervasyon TEK satır yazar (eşzamanlılık koruması); gerçek istek sayısı ancak çağrı
    bittikten sonra bilinir. Kayıt[0] rezervasyon satırını doldurur, kalan her kayıt için
    bir satır eklenir — böylece her satır KENDİ isteğinin sağlayıcısını, modelini,
    token'larını ve tahmini maliyetini taşır.

    Ek satırlar tavanı aşsa bile burada 429 ÜRETİLMEZ: istek zaten yapılmıştır, kullanıcıya
    yaptığı çağrının cevabı verilir; tavan bir sonraki istekte dayatılır.
    """
    if not olcum:
        return 0

    yazilan = 0
    try:
        ilk = 0
        if rezervasyon is not None:
            _satiri_doldur(rezervasyon, olcum[0], amac)
            ilk = 1
        for cagri in olcum[ilk:]:
            satir = ApiCallLog(user_id=user_id, provider=cagri.saglayici,
                               model=cagri.model or "?", status=ApiCallStatus.success,
                               tool_calls_count=0, duration_ms=0, amac=amac)
            _satiri_doldur(satir, cagri, amac)
            db.add(satir)
            yazilan += 1
        db.commit()
    except Exception as e:  # noqa: BLE001 — muhasebe isteği kirletmez
        logger.warning("LLM cagri satirlari yazilamadi: %s", e)
        db.rollback()
        return 0
    return yazilan


def rezerve_et(db: Session, user_id: int, provider: str, model: str,
               tavan: Optional[int] = None, hata_firlat: bool = True,
               amac: str = AMAC_KOC) -> Optional[ApiCallLog]:
    """Çağrı ÖNCESİ sayaç satırı yazar. Tavan aşılıyorsa rezervasyonu geri alır.

    `hata_firlat=True` → 429 HTTPException (kullanıcı-tetikli uçlar).
    `hata_firlat=False` → None döner (arka plan görevleri: kullanıcıya hata gösterilemez,
    yapılacak doğru şey işi ATLAMAKTIR — sessizce kotasız çağırmak değil).

    BUG #274: `provider`/`model` burada YAPILANDIRMADAN gelir (çağrı henüz yapılmadı,
    zincirde kimin cevaplayacağı bilinmez); gerçek değerler `ek_cagrilari_uzlastir` ile
    ölçümden yazılır. `amac` ise baştan bellidir ve kendi sütununa yazılır.
    """
    kisisel_tavan = kullanici_gunluk_tavan() if tavan is None else tavan
    log = ApiCallLog(
        user_id=user_id, provider=(provider or "?").lower(), model=model,
        status=ApiCallStatus.failed,   # çağrı bitince success'e çevrilir (çöken istek de sayılır)
        tool_calls_count=0, duration_ms=0, amac=amac,
    )
    db.add(log)
    db.commit()

    if kisisel_tavan:
        sira = (
            db.query(func.count(ApiCallLog.id))
            .filter(ApiCallLog.user_id == user_id,
                    ApiCallLog.called_at >= _gun_baslangici(),
                    ApiCallLog.id <= log.id)
            .scalar() or 0
        )
        if sira > kisisel_tavan:
            iptal_et(db, log)
            if hata_firlat:
                raise HTTPException(status_code=429, detail=KOTA_MESAJI)
            return None
    return log


def iptal_et(db: Session, log: Optional[ApiCallLog]) -> None:
    """Rezervasyonu geri al — LLM HİÇ çağrılmadıysa (ör. önbellekten dönüldü).

    Kullanıcı yapılmamış bir çağrı için cezalandırılmaz.
    """
    if log is None:
        return
    try:
        db.delete(log)
        db.commit()
    except Exception as e:  # noqa: BLE001 — muhasebe temizliği isteği kirletmez
        logger.warning("kota rezervasyonu iptal edilemedi: %s", e)
        db.rollback()


def tamamla(db: Session, log: Optional[ApiCallLog], provider: Optional[str] = None,
            success: bool = True, duration_ms: int = 0, tool_calls_count: int = 0,
            error_message: Optional[str] = None) -> None:
    """Rezerve edilen satırı çağrı sonucuyla günceller (BUG #212)."""
    if log is None:
        return
    try:
        log.provider = (provider or log.provider or "?").lower()
        log.status = ApiCallStatus.success if success else ApiCallStatus.failed
        log.duration_ms = duration_ms
        log.tool_calls_count = tool_calls_count
        # SEC-009: ham sağlayıcı hatası 300 karakterle sınırlı (KVKK export'una girer).
        # BUG #258 fix: KISALTMAK MASKELEMEK DEĞİLDİR. Sağlayıcı istisnaları çoğu zaman
        # isteğin kendisini taşır — `...?key=AIza...`, `Authorization: Bearer ...`, hatta
        # kullanıcının cümlesi. Bunlar DB'ye yazılıyordu ve `error_tracking.temizle`
        # zinciri yalnız LOG tarafına bağlıydı (BUG #244) — yani maskeleme vardı ama
        # KALICI yüzeye hiç ulaşmıyordu (L21). Maskeleme artık yazma sınırında.
        log.error_message = temizle(error_message, max_uzunluk=300) if error_message else None
        db.commit()
    except Exception as e:  # noqa: BLE001 — muhasebe güncellemesi isteği kirletmez
        logger.warning("ApiCallLog guncellemesi basarisiz: %s", e)
        db.rollback()
