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
- **CSP YÜZEYE GÖRE.** Uygulama iki farklı şey sunabilir ve ikisinin CSP'si aynı olamaz:
    · **Saf API** (varsayılan): `default-src 'none'` — cevap hiçbir alt kaynak yükleyemez.
    · **SPA da sunuluyorsa** (`SERVE_SPA=1`, BUG #284): aynı politika arayüzü ÖLDÜRÜR.

  BUG #287 — ÖLÇÜLEN DEFEKT (11 Ağu 2026, canlıda): kapalı beta Tailscale Funnel ile
  yayına alındı, uygulama SPA'yı kendisi servis etti ve tarayıcıda **bembeyaz ekran**
  çıktı. Dosyaların hepsi 200 dönüyordu; JS `default-src 'none'` tarafından engellenmişti.
  `#root` boştu, React hiç mount olmadı.

  **Bunu 17 testlik SPA kapısı YAKALAYAMADI** — çünkü `TestClient` CSP uygulamaz. CSP'yi
  yalnız gerçek bir tarayıcı zorlar. L29'un bu turdaki yüzü: *render edilip ölçülmeyen
  yüzey yoktur*; başlığın "gönderildiğini" test etmek, sayfanın AÇILDIĞINI ölçmez.

  SPA politikası nginx şablonuyla **birebir aynıdır** (kapı ikisinin eşitliğini assert
  eder): iki farklı dağıtım yolunda iki farklı güvenlik seviyesi olamaz.
- **Vekildeki başlık yine EZİLMEZ**; nginx varsa onunki geçerli kalır.
"""
from __future__ import annotations

import os
from typing import Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Saf API yüzeyi: cevap hiçbir alt kaynak yükleyemez.
CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

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
    "Content-Security-Policy": CSP_API,
}

# SPA sunulduğunda geçerli politika (BUG #287). `deploy/nginx*.template` ile BİREBİR AYNI
# olmalı — iki dağıtım yolu iki farklı güvenlik seviyesi üretemez (kapı bunu assert eder).
# `script-src 'self'`: inline script YOK — tema başlatıcı bu yüzden harici dosyaya taşındı
# (`frontend/public/theme-init.js`). CSP'yi 'unsafe-inline' ile gevşetmek yerine kod
# kurallara uygun yere taşındı (L51).
# `style-src 'unsafe-inline'`: React/Tailwind çalışma anında stil enjekte eder — bu satır
# olmadan arayüz stilsiz açılır. Bilinçli ve nginx tarafıyla aynı.
CSP_SPA = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)


def csp_degeri() -> str:
    """Yüzeye göre CSP. SPA sunuluyorsa API politikası arayüzü ÖLDÜRÜR (BUG #287)."""
    from app.spa import spa_aktif
    return CSP_SPA if spa_aktif() else CSP_API


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
                # BUG #287: CSP yüzeye göre belirlenir (SPA sunuluyorsa API politikası
                # arayüzü öldürür — canlıda bembeyaz ekran olarak ölçüldü).
                response.headers[ad] = csp_degeri() if ad == "Content-Security-Policy" else deger
        if hsts_acik_mi() and _https_mi(request) and "Strict-Transport-Security" not in response.headers:
            response.headers["Strict-Transport-Security"] = HSTS_DEGERI
        return response
