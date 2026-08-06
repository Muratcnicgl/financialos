"""
GÜVENLİK BAŞLIKLARI KAPISI (BUG #259 / SEC-005) — H22'nin ikinci uygulaması.

ÖLÇÜLEN DEFEKT (7 Ağu 2026)
---------------------------
HSTS / CSP / X-Frame-Options / nosniff / Referrer-Policy **yalnız** nginx şablonunda
tanımlıydı (`deploy/nginx*`, satır 76-80). Uygulama katmanında tek bir güvenlik başlığı
yoktu (`grep` ile ölçüldü: `app/` içinde 0 eşleşme).

Bu tam olarak **H22**'nin yasakladığı yapıdır: *"Hiçbir güvenlik sınırı tek katmanda
(ters vekilde) yaşamamalı — nginx atlanabilir, yapılandırma sessizce değişebilir."*
Aynı ders BUG #213'te gövde-boyutu sınırı için öğrenilmiş, başlıklar atlanmıştı.

Somut kaybolma senaryoları: systemd yolu (ADR-035 "alternatif"), doğrudan port yayını,
tünel/port-forward, staging'de vekilsiz koşum. Üçünde de korumanın tamamı yok olur.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security_headers import HSTS_DEGERI, TEMEL_BASLIKLAR

istemci = TestClient(app)


@pytest.mark.parametrize("baslik,deger", sorted(TEMEL_BASLIKLAR.items()))
def test_temel_basliklar_uygulama_katmaninda(baslik, deger):
    """Vekil OLMADAN da her yanıt korunur."""
    r = istemci.get("/api/health")
    assert r.headers.get(baslik) == deger, f"{baslik} eksik/yanlış: {r.headers.get(baslik)!r}"


def test_hata_yanitlarinda_da_var():
    """404/422 gibi yanıtlar da tarayıcıya gider — koruma orada da olmalı."""
    r = istemci.get("/api/boyle-bir-uc-yok")
    assert r.status_code == 404
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_hsts_yalniz_https_yolunda():
    """
    L6 (kapı ürünü kıramaz): `http://` üzerinden HSTS göndermek yerel geliştirmede
    tarayıcıyı o hosta kilitler. Ters vekil arkasında `X-Forwarded-Proto` kabul edilir.
    """
    duz = istemci.get("/api/health")
    assert "Strict-Transport-Security" not in duz.headers

    vekil = istemci.get("/api/health", headers={"X-Forwarded-Proto": "https"})
    assert vekil.headers.get("Strict-Transport-Security") == HSTS_DEGERI


def test_vekilin_basligi_ezilmez():
    """
    nginx daha SIKI bir politika koyuyorsa uygulama onu ezmemeli (çift katman çatışmaz).
    Middleware'in davranışı: başlık zaten varsa dokunma.
    """
    from starlette.responses import JSONResponse

    from app.security_headers import GuvenlikBasliklariMiddleware

    class _SahteIstek:
        url = type("u", (), {"scheme": "http"})()
        headers: dict = {}

    async def _cagir(_):
        cevap = JSONResponse({"ok": True})
        cevap.headers["Content-Security-Policy"] = "default-src 'self'"  # vekilin sıkı politikası
        return cevap

    mw = GuvenlikBasliklariMiddleware(app=None)
    import asyncio
    cevap = asyncio.run(mw.dispatch(_SahteIstek(), _cagir))
    assert cevap.headers["Content-Security-Policy"] == "default-src 'self'"
    assert cevap.headers["X-Frame-Options"] == "DENY"  # eksik olan yine de eklenir


def test_nginx_ve_uygulama_ayni_baslik_kumesini_taşiyor():
    """
    İki katman AYRIŞMAMALI: nginx şablonunda olan her güvenlik başlığının uygulama
    karşılığı da bulunmalı (yoksa vekilsiz kurulumda sessizce eksik kalır — L27).
    """
    import re
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent.parent
    adaylar = list((kok / "deploy").rglob("nginx*")) if (kok / "deploy").exists() else []
    sablonlar = [p for p in adaylar if p.is_file()]
    assert sablonlar, "nginx şablonu bulunamadı — kapı ölçtüğünü bulamıyor"

    nginx_basliklar = set()
    for p in sablonlar:
        for m in re.finditer(r'add_header\s+([A-Za-z\-]+)\s', p.read_text(encoding="utf-8")):
            nginx_basliklar.add(m.group(1))

    uygulama = set(TEMEL_BASLIKLAR) | {"Strict-Transport-Security"}
    eksik = {b for b in nginx_basliklar
             if b not in uygulama and b.lower() not in {"x-robots-tag", "cache-control"}}
    assert not eksik, f"nginx'te olup uygulamada olmayan güvenlik başlığı: {sorted(eksik)}"
    assert len(nginx_basliklar) >= 4, "nginx şablonu taraması çökmüş olabilir (kapsam tabanı)"
