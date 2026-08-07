"""
Kapasite sınırları — TEK KAYNAK (P5.5, BUG #263).

SORUN (ölçüldü, varsayım değil):
Uygulamanın 114 HTTP ucunun **tamamı** senkron (`def`) — yani her istek Starlette/anyio
iş parçacığı havuzunda koşar (varsayılan **40 token/process**). Her istek `Depends(get_db)`
ile bir DB oturumu alır ve oturum, isteğin SONUNA kadar bağlantıyı elde tutar.
Prod'daki PostgreSQL havuzu ise process başına **15** bağlantıdır (`pool_size 5 + overflow 10`).

Yani uygulamanın eşzamanlılığı (40) DB kapasitesini (15) **kat kat aşıyordu**. Sonuç zinciri:

  1. Koç isteği iki LLM çağrısı yapar (iki-geçiş mimarisi); bu sırada DB bağlantısı
     **elde tutulur** (oturum açık). Tek bir koç isteği 10-40 sn bağlantı işgal eder.
  2. 15 eşzamanlı yavaş istek havuzu tamamen kilitler.
  3. 16. istek `pool_timeout` (varsayılan **30 sn**) boyunca bekler, sonra
     `QueuePool limit ... reached` ile **500** döner — kullanıcı "Beklenmedik hata" görür.
  4. `/api/ready` de havuzdan bağlantı ister → o da 30 sn asılır → Docker HEALTHCHECK
     zaman aşımına uğrar → **konteyner sağlıksız işaretlenir / yeniden başlar** →
     uçuştaki tüm istekler ölür. Kaskad.

`app/database.py`'deki kapasite muhakemesi yalnız **Postgres `max_connections`** tarafına
bakıyordu (`2 worker × 15 + scheduler = 45 < 100`). O taraf doğruydu; ama uygulamanın
KENDİ içinde havuzun daha önce tükeneceği hiç hesaba katılmamıştı.

KARAR — sırt basıncı kaynağa konur, DB'ye yıkılmaz:
  - Havuzu 40'a çıkarmak maliyeti DB'ye yıkardı (2×40+ bağlantı, küçük VM'de bellek).
  - Doğru desen: **uygulama eşzamanlılığı ≤ DB havuzu** ve **yavaş yollar ≪ havuz**,
    böylece hızlı uçlar (cockpit, /api/ready) için her zaman boş slot kalır.

UYGULAMA:
  - İş parçacığı havuzu başlangıçta DB kapasitesine indirilir (`uygula()`), yani havuz
    tükenmesi yapısal olarak imkânsız hale gelir; fazla istek anyio kuyruğunda bekler.
  - Yavaş yollar (LLM, dış servis) **adlandırılmış tavanlarla** sınırlanır; tavan doluysa
    istek beklemez — anında `KapasiteDolu` (503 + Retry-After). Beklemek iş parçacığını
    VE DB bağlantısını tutmak demektir; reddetmek daha ucuz ve daha dürüsttür.
  - Değişmez (`dogrula()`): `yavaş tavanların toplamı + hızlı-yol rezervi ≤ DB kapasitesi`.
    Production'da ihlal = açılışta fail-fast (canlıda ilk yük anında öğrenmek yerine).

Env: DB_POOL_SIZE · DB_MAX_OVERFLOW · LLM_MAX_CONCURRENCY · DIS_SERVIS_MAX_CONCURRENCY
     THREADPOOL_TOKENS · MIN_HIZLI_SLOT
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

# Yavaş yol adları — sabit; yeni ad eklemek TAVANLAR'a da satır ekler (aksi halde
# sessizce sınırsız çalışır: L26 "yasağın gücü kaynağı seçen kod sayısı kadardır").
LLM = "llm"
DIS_SERVIS = "dis_servis"
EPOSTA = "eposta"

_VARSAYILAN_TAVAN = {
    # Koç mesajı başına 2 LLM çağrısı (iki-geçiş) × 10-40 sn. 3 eşzamanlı koç, kapalı
    # betanın (3-10 davetli) gerçek kullanımının çok üstünde; havuzun beşte biri.
    LLM: ("LLM_MAX_CONCURRENCY", 3),
    # TCMB EVDS 30 sn timeout'lu senkron çağrı (BUG #246). Panelin açılışta çektiği
    # birkaç kur bu tavanın altında kalır.
    DIS_SERVIS: ("DIS_SERVIS_MAX_CONCURRENCY", 3),
    # SMTP (STARTTLS el sıkışması + login + gönderim, 20 sn timeout). Kendi yolu olması
    # BİLİNÇLİ: EVDS çökmesi şifre-sıfırlama e-postasını engellememelidir — kur bilgisi
    # kozmetiktir, hesabına giremeyen kullanıcı kilitlenmiştir.
    EPOSTA: ("EPOSTA_MAX_CONCURRENCY", 2),
}

# Slot yokken beklenecek azami süre (saniye). Varsayılan 0 = hiç bekleme.
_BEKLEME = {
    # E-posta tek istisnadır. Gerekçe: (a) üç gönderimin üçü de `BackgroundTasks` ile
    # YANIT SONRASI koşar — ne bekleyen bir istemci ne de açık bir DB oturumu vardır,
    # yani beklemenin bedeli yalnız bir iş parçacığıdır; (b) düşen bir şifre-sıfırlama
    # e-postası kullanıcıyı hesabının DIŞINDA bırakır — kısa beklemek bunu önlemek için
    # ucuz bir bedeldir. LLM/dış-servis yollarında ise bekleyen bir kullanıcı vardır ve
    # beklemek DB bağlantısını tutmaya devam etmek demektir → onlarda bekleme YOK.
    EPOSTA: ("EPOSTA_BEKLEME_SANIYE", 5.0),
}

# Yavaş yollar havuzu bitirmesin: hızlı uçlar (cockpit, /api/ready, auth) için ayrılan
# asgari slot. Bu sayı ürünün "yük altında da açık kalır" sözüdür.
_MIN_HIZLI_SLOT_VARSAYILAN = 6


class KapasiteDolu(Exception):
    """Yavaş yol tavanı dolu — istek reddedildi (503, geçici).

    Bu bir HATA DEĞİL, bilinçli bir sırt basıncı kararıdır: `app/main.py`'deki genel
    `Exception` yakalayıcısına düşmemesi için ayrı bir handler'ı vardır (aksi halde
    `error_logs`'a "beklenmedik hata" olarak yazılır ve gerçek arızaları gürültüye boğar).
    """

    def __init__(self, ad: str, tavan: int, tekrar_saniye: int = 5) -> None:
        self.ad = ad
        self.tavan = tavan
        self.tekrar_saniye = tekrar_saniye
        super().__init__(f"kapasite dolu: {ad} (tavan={tavan})")


def _int_env(ad: str, varsayilan: int) -> int:
    ham = os.getenv(ad)
    if ham is None or not ham.strip():
        return varsayilan
    try:
        return int(ham)
    except ValueError:
        logger.warning("[kapasite] %s=%r sayı değil → varsayılan %s", ad, ham, varsayilan)
        return varsayilan


def tavan(ad: str) -> int:
    env_ad, varsayilan = _VARSAYILAN_TAVAN[ad]
    return max(1, _int_env(env_ad, varsayilan))


def bekleme(ad: str) -> float:
    """Slot yokken beklenecek azami süre (0 = hiç bekleme, anında reddet)."""
    kayit = _BEKLEME.get(ad)
    if kayit is None:
        return 0.0
    env_ad, varsayilan = kayit
    ham = os.getenv(env_ad)
    if ham is None or not ham.strip():
        return varsayilan
    try:
        return max(0.0, float(ham))
    except ValueError:
        logger.warning("[kapasite] %s=%r sayı değil → varsayılan %s", env_ad, ham, varsayilan)
        return varsayilan


def min_hizli_slot() -> int:
    return max(0, _int_env("MIN_HIZLI_SLOT", _MIN_HIZLI_SLOT_VARSAYILAN))


def db_havuz_kapasitesi() -> Optional[int]:
    """Process başına DB bağlantı tavanı; havuzlanmayan dialect'te None.

    SQLite (dev) için None döner: dosya-tabanlı SQLite'ta darboğaz bağlantı sayısı değil
    yazma kilididir (WAL + busy_timeout, BUG #060). Kapasite muhakemesi prod dialect'i
    olan PostgreSQL içindir; ölçüt uydurup SQLite'ı gereksiz yere daraltmayız.
    """
    from app.database import IS_POSTGRES  # lazy: import döngüsü yok
    if not IS_POSTGRES:
        return None
    return _int_env("DB_POOL_SIZE", 5) + _int_env("DB_MAX_OVERFLOW", 10)


def threadpool_tokens() -> Optional[int]:
    """Uygulanacak iş parçacığı havuzu büyüklüğü; None = anyio varsayılanına dokunma."""
    acik = os.getenv("THREADPOOL_TOKENS")
    if acik and acik.strip():
        return max(1, _int_env("THREADPOOL_TOKENS", 40))
    return db_havuz_kapasitesi()   # Postgres'te havuza eşitle, SQLite'ta dokunma


# ---------------------------------------------------------------- semaforlar

_semaforlar: dict[str, threading.BoundedSemaphore] = {}
_semafor_tavani: dict[str, int] = {}
_kilit = threading.Lock()


def _semafor(ad: str) -> threading.BoundedSemaphore:
    """Ad başına tek semafor. Tavan env ile değişirse semafor yeniden kurulur (test kolaylığı)."""
    t = tavan(ad)
    with _kilit:
        if _semafor_tavani.get(ad) != t:
            _semaforlar[ad] = threading.BoundedSemaphore(t)
            _semafor_tavani[ad] = t
        return _semaforlar[ad]


@contextmanager
def yavas_yol(ad: str) -> Iterator[None]:
    """Yavaş bir dış çağrıyı kapasite slotu altında koştur.

    Slot yoksa varsayılan olarak **beklemez** — `KapasiteDolu` fırlatır. Beklemek, bu iş
    parçacığını ve (çağıran uçta açık olan) DB bağlantısını tutmaya devam etmek demektir;
    tam da kaçınmak istediğimiz şey odur. Tek istisna `_BEKLEME` tablosundadır ve gerekçesi
    orada yazılıdır — bekleme süresi yola göre belirlenir, çağrı yerine bırakılmaz (aksi
    halde "acelesi olan" her çağrı kendi istisnasını yazar ve kural erir).
    """
    sem = _semafor(ad)
    bekle = bekleme(ad)
    alindi = sem.acquire(timeout=bekle) if bekle > 0 else sem.acquire(blocking=False)
    if not alindi:
        logger.warning("[kapasite] %s tavanı dolu (tavan=%s, bekleme=%ss) — istek reddedildi",
                       ad, tavan(ad), bekle)
        raise KapasiteDolu(ad, tavan(ad))
    try:
        yield
    finally:
        sem.release()


def bos_slot(ad: str) -> int:
    """Şu an boş slot sayısı (gözlem/test için; yarış koşulsuz kesinlik iddia etmez)."""
    sem = _semafor(ad)
    return getattr(sem, "_value", 0)


# ---------------------------------------------------------------- doğrulama

def ihlaller() -> list[str]:
    """Kapasite değişmezinin ihlalleri (boş liste = tutarlı)."""
    sorunlar: list[str] = []
    kapasite = db_havuz_kapasitesi()
    if kapasite is None:
        return sorunlar   # havuzlanmayan dialect: muhakeme uygulanmaz

    yavas_toplam = sum(tavan(a) for a in _VARSAYILAN_TAVAN)
    rezerv = min_hizli_slot()
    if yavas_toplam + rezerv > kapasite:
        sorunlar.append(
            f"yavaş yol tavanları ({yavas_toplam}) + hızlı-yol rezervi ({rezerv}) "
            f"> DB havuz kapasitesi ({kapasite}): yük altında hızlı uçlar da havuz "
            f"bekleyip 500 döner. LLM_MAX_CONCURRENCY/DIS_SERVIS_MAX_CONCURRENCY düşür "
            f"ya da DB_POOL_SIZE/DB_MAX_OVERFLOW artır."
        )

    tokens = threadpool_tokens()
    if tokens is not None and tokens > kapasite:
        sorunlar.append(
            f"iş parçacığı havuzu ({tokens}) > DB havuz kapasitesi ({kapasite}): "
            f"eşzamanlı istek sayısı bağlantı sayısını aşar → QueuePool zaman aşımı (500). "
            f"THREADPOOL_TOKENS düşür ya da DB havuzunu büyüt."
        )
    return sorunlar


def dogrula() -> None:
    """Açılışta kapasite tutarlılığını denetle.

    Production'da ihlal **fail-fast**'tir: yanlış yapılandırma canlıda ancak ilk yükte,
    yani gerçek kullanıcı 500 gördüğünde ortaya çıkardı (BUG #157'nin öğrettiği desen).
    Dev'de yalnız uyarı — geliştirmeyi kilitlemez (L6).
    """
    sorunlar = ihlaller()
    if not sorunlar:
        return
    from app.settings import is_production
    metin = " | ".join(sorunlar)
    if is_production():
        raise RuntimeError(f"Kapasite yapılandırması tutarsız: {metin}")
    logger.warning("[kapasite] %s", metin)


def uygula() -> Optional[int]:
    """İş parçacığı havuzunu kapasiteye göre ayarla. Uygulanan değeri döner (None = dokunulmadı)."""
    tokens = threadpool_tokens()
    if tokens is None:
        return None
    try:
        from anyio.to_thread import current_default_thread_limiter
        current_default_thread_limiter().total_tokens = tokens
    except Exception as e:  # noqa: BLE001 — anyio sürümü/çalışma-anı dışı: sessiz kalma, logla
        logger.warning("[kapasite] iş parçacığı havuzu ayarlanamadı: %s: %s", type(e).__name__, e)
        return None
    logger.info("[kapasite] iş parçacığı havuzu = %s (DB havuzu ile hizalandı)", tokens)
    return tokens


def durum() -> dict:
    """Gözlemlenebilirlik: kapasite ayarları + o anki doluluk."""
    return {
        "db_havuzu": db_havuz_kapasitesi(),
        "is_parcacigi_havuzu": threadpool_tokens(),
        "min_hizli_slot": min_hizli_slot(),
        "yavas_yollar": {a: {"tavan": tavan(a), "bos": bos_slot(a)} for a in _VARSAYILAN_TAVAN},
        "tutarli": not ihlaller(),
    }


def havuz_doygun_mu() -> bool:
    """DB havuzu şu an tamamen mi kullanımda (bağlantı İSTEMEDEN ölçülür).

    `/api/ready` bunu bilmeden `SELECT 1` denerse havuz doluyken `pool_timeout` kadar
    (30 sn) asılır ve HEALTHCHECK zaman aşımına uğrar. Doygunluğu önceden görüp hızlıca
    503 dönmek, konteyneri gereksiz yere yeniden başlatmaktan iyidir.
    """
    from app.database import engine
    havuz = getattr(engine, "pool", None)
    kapasite = db_havuz_kapasitesi()
    if havuz is None or kapasite is None:
        return False
    try:
        return havuz.checkedout() >= kapasite
    except Exception:  # noqa: BLE001 — havuz tipi checkedout() desteklemiyorsa ölçme
        return False
