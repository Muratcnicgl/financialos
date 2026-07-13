"""
M21 — Auth endpoint rate limiting (in-memory per-IP sliding window, per-bucket).

Production değerleri (OWASP brute-force koruması). Slowapi yerine mevcut hafif limiter
genişletildi (yeni bağımlılık yok, KURAL 12). Wave-4: çok-instance için Redis'e taşınır.

Env override (opsiyonel): RATE_LIMIT_<BUCKET>_MAX / RATE_LIMIT_<BUCKET>_WINDOW.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

# (max_istek, pencere_saniye) — production varsayılanları
_DEFAULTS = {
    "login": (5, 900),       # 5 / 15 dakika (brute-force)
    "register": (3, 3600),   # 3 / saat (spam hesap)
    "pwreset": (3, 3600),    # 3 / saat (e-posta bombing)
    "oauth": (10, 60),       # 10 / dakika
}

_RATE: dict[str, deque] = defaultdict(deque)


def limit_for(bucket: str) -> tuple[int, int]:
    max_d, win_d = _DEFAULTS.get(bucket, (10, 60))
    b = bucket.upper()
    return (
        int(os.getenv(f"RATE_LIMIT_{b}_MAX", str(max_d))),
        int(os.getenv(f"RATE_LIMIT_{b}_WINDOW", str(win_d))),
    )


def rate_limit(request: Request, bucket: str) -> None:
    """Bucket + IP başına sliding window. Aşımda 429."""
    max_r, window = limit_for(bucket)
    ip = request.client.host if request.client else "unknown"
    key = f"{bucket}:{ip}"
    now = time.monotonic()
    q = _RATE[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_r:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla deneme. Lütfen bir süre sonra tekrar deneyin.",
        )
    q.append(now)


def reset() -> None:
    """Test yardımcısı — sayaçları sıfırlar."""
    _RATE.clear()
