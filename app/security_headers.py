"""
GÜVENLİK BAŞLIKLARI — uygulama katmanı (SEC-005 / BUG #259).

NEDEN UYGULAMA KATMANINDA
-------------------------
Başlıklar (HSTS, CSP, X-Frame-Options, nosniff, Referrer-Policy) yalnız nginx şablonunda
tanımlıydı. Bu tam olarak **H22**'nin yasakladığı durumdur: *"Hiçbir güvenlik sınırı tek
katmanda (ters vekilde) yaşamamalı — nginx atlanabilir, yapılandırma sessizce değişebilir."*
Aynı ders BUG #213'te gövde boyutu sınırı için öğrenilmişti (`app/request_limits.py`);
başlıklar o turda atlanmıştı.

Somut senaryolar: (a) uygulama doğrudan bir porttan yayınlanırsa (systemd yolu, tünel,
container port map), (b) nginx şablonu elle düzenlenirse, (c) geliştirme/staging'de vekil
yoksa. Üçünde de korumanın tamamı kaybolur.

TASARIM
-------
- **Vekildeki başlığı EZMEZ.** Zaten set edilmiş bir başlığa dokunulmaz; nginx daha sıkı bir
  politika uyguluyorsa o kalır (çift-katman çatışmaz).
- **HSTS yalnız HTTPS'te.** `http://` üzerinden HSTS göndermek anlamsızdır ve yerel
  geliştirmede tarayıcıyı kilitler (L6: kapı ürünü kıramaz). Ters vekil arkasında
  `X-Forwarded-Proto: https` de kabul edilir.
- **CSP API için dar.** Bu uygulama JSON API'si sunar; HTML yalnız `/docs` (prod'da kapalı).
  Bu yüzden varsayılan `default-src 'none'` + `frame-ancestors 'none'`. Statik arayüzü nginx
  sunar ve kendi (daha geniş) CSP'sini uygular — o başlık burada EZİLMEZ.
"""
from __future__ import annotations

import os
from typing import Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# API yanıtları için sabit başlıklar. Değer değişirse `tests/security/test_guvenlik_basliklari.py`
# kırılır (iddia belge değil, kapı).
TEMEL_BASLIKLAR: Dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    # API'nin kendi cevabı hiçbir alt kaynağı yükleyemez; hiçbir sayfa onu çerçeveleyemez.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}

HSTS_DEGERI = "max-age=31536000; includeSubDomains"


def _https_mi(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    # Ters vekil arkasında şema başlıkta gelir.
    return (request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower() == "https")


def hsts_acik_mi() -> bool:
    """HSTS'i açıkça kapatma kaçışı (yerel HTTPS denemeleri için); varsayılan AÇIK."""
    return os.getenv("HSTS_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


class GuvenlikBasliklariMiddleware(BaseHTTPMiddleware):
    """Her yanıta güvenlik başlıklarını ekler; var olanı EZMEZ."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for ad, deger in TEMEL_BASLIKLAR.items():
            if ad not in response.headers:
                response.headers[ad] = deger
        if hsts_acik_mi() and _https_mi(request) and "Strict-Transport-Security" not in response.headers:
            response.headers["Strict-Transport-Security"] = HSTS_DEGERI
        return response
