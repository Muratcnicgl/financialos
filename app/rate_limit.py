"""
M21 — Auth endpoint rate limiting (per-IP sliding window, per-bucket).

Production değerleri (OWASP brute-force koruması). Slowapi yerine mevcut hafif limiter
genişletildi (yeni bağımlılık yok, KURAL 12).

GUNCELLEMELER:
  BUG #182 fix (P2, Wave-9) — limiter iki yerden birden kırıktı:

    (a) İSTEMCİ IP'Sİ: `request.client.host` kullanılıyordu. Prod'da nginx AYRI konteynerden
        proxy'lediği için bu değer her istekte nginx'in IP'siydi → tüm kullanıcılar TEK
        kovaya düşüyordu. Bir saldırgan 5 hatalı login ile herkesin girişini 15 dk kilitler
        (DoS); gerçek brute-force koruması ise kullanıcı ayrımı olmadığı için anlamsızlaşır.
        Artık `TRUST_PROXY_HEADERS` açıkken X-Forwarded-For zincirinin **en sağdaki** değeri
        kullanılır — bu, bizim nginx'imizin eklediği gerçek peer'dır ve istemci uyduramaz
        (en soldaki değer istemci kontrolündedir, kullanılmaz).

    (b) ÇOK-WORKER: sayaçlar process-yerel sözlükteydi; gunicorn `--workers 2+` ile her
        worker kendi sayacını tuttuğundan ilan edilen limit worker sayısı kadar katlanıyordu
        ve her restart sayaçları sıfırlıyordu. DB oturumu verildiğinde sayaç `rate_limit_hits`
        tablosunda tutulur → tüm worker'lar aynı pencereyi görür, restart hafızayı silmez.
        DB verilmezse (dev/test/iç çağrı) eski bellek yoluna düşer.

Env: RATE_LIMIT_<BUCKET>_MAX / RATE_LIMIT_<BUCKET>_WINDOW · TRUST_PROXY_HEADERS=1
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status

# (max_istek, pencere_saniye) — production varsayılanları
_DEFAULTS = {
    "login": (5, 900),       # 5 / 15 dakika (brute-force)
    "register": (3, 3600),   # 3 / saat (spam hesap)
    "pwreset": (3, 3600),    # 3 / saat (e-posta bombing)
    "oauth": (10, 60),       # 10 / dakika
    "invite": (10, 3600),    # 10 / saat (davet spam'i — BUG #183)
    # BUG #246 (D32): fiyat uçları DIŞ servise (TCMB EVDS) senkron çağrı yapar; kimlik
    # artık zorunlu ama tek bir kullanıcı da operatörün dış kotasını yakabilir/threadpool'u
    # doldurabilir. Panelin gerçek kullanımı (açılışta birkaç kur) bu tavanın çok altında.
    "prices": (30, 60),      # 30 / dakika
}

_RATE: dict[str, deque] = defaultdict(deque)


def limit_for(bucket: str) -> tuple[int, int]:
    max_d, win_d = _DEFAULTS.get(bucket, (10, 60))
    b = bucket.upper()
    return (
        int(os.getenv(f"RATE_LIMIT_{b}_MAX", str(max_d))),
        int(os.getenv(f"RATE_LIMIT_{b}_WINDOW", str(win_d))),
    )


def _trust_proxy() -> bool:
    return os.getenv("TRUST_PROXY_HEADERS", "").strip().lower() in ("1", "true", "yes")


def client_ip(request: Request) -> str:
    """BUG #182 (a): gerçek istemci IP'si.

    Ters-proxy arkasındaysak (TRUST_PROXY_HEADERS=1) X-Forwarded-For zincirinin EN SAĞDAKİ
    değeri bizim proxy'mizin eklediği peer'dır → istemci tarafından uydurulamaz. Aksi
    hâlde başlığa hiç güvenilmez (aksi takdirde herkes limiti atlatabilirdi).
    """
    if _trust_proxy():
        xff = request.headers.get("x-forwarded-for", "")
        parcalar = [p.strip() for p in xff.split(",") if p.strip()]
        if parcalar:
            return parcalar[-1]
    return request.client.host if request.client else "unknown"


def _limit_memory(key: str, max_r: int, window: int) -> bool:
    """True = limit aşıldı. (Process-yerel; dev/test ve DB'siz çağrılar için.)"""
    now = time.monotonic()
    q = _RATE[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_r:
        return True
    q.append(now)
    return False


def _limit_db(db, key: str, max_r: int, window: int) -> bool:
    """True = limit aşıldı. Sayaç DB'de → tüm worker'lar aynı pencereyi görür.

    Önce yaz-sonra-say: eşzamanlı iki worker'da sayım güvenli tarafa (fazla saymaya)
    kayar; hiçbir durumda limitin altında kalmaz.
    """
    from app.models import RateLimitHit
    simdi = datetime.now(timezone.utc).replace(tzinfo=None)
    esik = simdi - timedelta(seconds=window)
    try:
        db.query(RateLimitHit).filter(
            RateLimitHit.bucket_key == key, RateLimitHit.hit_at < esik
        ).delete(synchronize_session=False)
        db.add(RateLimitHit(bucket_key=key, hit_at=simdi))
        db.commit()
        sayi = db.query(RateLimitHit).filter(
            RateLimitHit.bucket_key == key, RateLimitHit.hit_at >= esik
        ).count()
    except Exception:
        # Limiter uygulamayı ASLA düşürmemeli — DB sorununda bellek yoluna düş.
        db.rollback()
        return _limit_memory(key, max_r, window)
    return sayi > max_r


def rate_limit(request: Request, bucket: str, db=None) -> None:
    """Bucket + istemci IP'si başına sliding window. Aşımda 429.

    `db` verilirse sayaç paylaşılan (çok-worker güvenli) DB'de tutulur.
    """
    max_r, window = limit_for(bucket)
    key = f"{bucket}:{client_ip(request)}"
    asildi = _limit_db(db, key, max_r, window) if db is not None else \
        _limit_memory(key, max_r, window)
    if asildi:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla deneme. Lütfen bir süre sonra tekrar deneyin.",
        )


def reset(db=None) -> None:
    """Test yardımcısı — sayaçları sıfırlar."""
    _RATE.clear()
    if db is not None:
        from app.models import RateLimitHit
        db.query(RateLimitHit).delete()
        db.commit()
