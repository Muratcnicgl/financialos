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


def test_tunel_sablonu_YONLENDIRME_yapmaz():
    """BUG #283 (B4): tünel arkasında `return 301 https://...` SONSUZ DÖNGÜ üretir.

    Tünel yollarında (Cloudflare Tunnel / Tailscale Funnel) TLS DIŞARIDA sonlanır ve
    nginx'e düz HTTP gelir. VPS şablonundaki koşulsuz 301, zaten HTTPS olan bir isteği
    tekrar HTTPS'e yönlendirir → tarayıcı döngüye girer ve uygulama HİÇ açılmaz.

    Bu defekt ilk yazdığım Cloudflare runbook'unda vardı (`service: http://localhost:80`)
    ve ancak nginx şablonu okunduğunda görüldü — belge doğru görünüyordu, kod hayır.
    """
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent.parent
    tunel = kok / "deploy" / "nginx.tunnel.conf.template"
    assert tunel.exists(), "Tünel şablonu yok — tünel modu deploy edilemez"

    metin = tunel.read_text(encoding="utf-8")
    kod = "\n".join(s for s in metin.splitlines() if not s.strip().startswith("#"))
    assert "return 301" not in kod, (
        "Tünel şablonunda 301 yönlendirme var — tünel arkasında sonsuz döngü üretir"
    )
    assert "listen 443 ssl" not in kod, (
        "Tünel şablonu TLS sonlandırıyor — sertifika dış katmanda, burada olmamalı"
    )


def test_tunel_sablonu_X_Forwarded_Proto_HTTPS_sabitler():
    """Dış hop gerçekten HTTPS'tir; `$scheme` yazılırsa uygulama isteği HTTP sanır.

    Sonucu sessizdir ve ikilidir: HSTS gönderilmez ve `secure` çerez mantığı yanlış
    tarafa düşer. Sabit `https` yazmak burada doğru olandır — TLS'i dış katman garanti eder.
    """
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent.parent
    metin = (kok / "deploy" / "nginx.tunnel.conf.template").read_text(encoding="utf-8")
    kod = "\n".join(s for s in metin.splitlines() if not s.strip().startswith("#"))
    assert "proxy_set_header X-Forwarded-Proto https;" in kod
    assert "X-Forwarded-Proto $scheme" not in kod, (
        "Tünel şablonu $scheme kullanıyor — düz HTTP geldiği için 'http' yazar"
    )


def test_iki_nginx_sablonu_AYNI_baslik_kumesini_tasir():
    """VPS ve tünel şablonları ayrışmamalı: birinde sertleştirme yapılıp diğeri unutulursa
    hangi modda koştuğuna göre güvenlik seviyesi DEĞİŞİR — ve bunu kimse fark etmez."""
    import re
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent.parent / "deploy"

    def basliklar(dosya: str) -> set[str]:
        return {m.group(1) for m in re.finditer(
            r'add_header\s+([A-Za-z\-]+)\s', (kok / dosya).read_text(encoding="utf-8"))}

    vps = basliklar("nginx.conf.template")
    tunel = basliklar("nginx.tunnel.conf.template")
    assert vps == tunel, (
        f"İki nginx şablonu ayrışmış.\n  Yalnız VPS'te: {sorted(vps - tunel)}\n"
        f"  Yalnız tünelde: {sorted(tunel - vps)}"
    )


# ══════════════════════════════════════════════════════════════════════
# BUG #287 — CSP YÜZEYE GÖRE (canlıda bembeyaz ekran olarak ölçüldü)
# ══════════════════════════════════════════════════════════════════════

def test_SPA_modunda_CSP_arayuzu_OLDURMEZ(monkeypatch):
    """Kapalı beta yayına alındığında tarayıcıda BEMBEYAZ EKRAN çıktı.

    Dosyaların hepsi 200 dönüyordu; `default-src 'none'` JS'i engelliyordu, `#root` boştu,
    React hiç mount olmadı. 17 testlik SPA kapısı bunu göremedi çünkü `TestClient` CSP
    UYGULAMAZ — CSP'yi yalnız gerçek tarayıcı zorlar (L29).
    """
    monkeypatch.setenv("SERVE_SPA", "1")
    from app.security_headers import csp_degeri
    politika = csp_degeri()
    assert "default-src 'none'" not in politika, "SPA modunda CSP arayüzü öldürüyor"
    assert "script-src 'self'" in politika, "SPA'nın kendi JS'i yüklenemez"
    assert "connect-src 'self'" in politika, "Arayüz kendi API'sine istek atamaz"


def test_API_modunda_CSP_DAR_kalir(monkeypatch):
    """SPA kapalıyken saf API politikası korunur — gevşetme SPA'ya özgüdür."""
    monkeypatch.delenv("SERVE_SPA", raising=False)
    from app.security_headers import csp_degeri
    assert "default-src 'none'" in csp_degeri()


def test_SPA_CSP_si_nginx_ile_AYNI():
    """İki dağıtım yolu iki farklı güvenlik seviyesi üretemez.

    Uygulama SPA'yı kendi servis ettiğinde (tünel yolu) ve nginx servis ettiğinde (VPS yolu)
    tarayıcının gördüğü politika AYNI olmalı; biri sertleştirilip diğeri unutulursa
    korumanın gücü hangi yolla deploy edildiğine göre DEĞİŞİR ve bunu kimse fark etmez.
    """
    import re
    from pathlib import Path

    from app.security_headers import CSP_SPA

    kok = Path(__file__).resolve().parent.parent.parent
    sablon = (kok / "deploy" / "nginx.conf.template").read_text(encoding="utf-8")
    m = re.search(r'add_header\s+Content-Security-Policy\s+"([^"]+)"', sablon)
    assert m, "nginx şablonunda CSP bulunamadı — kapı ölçtüğünü bulamıyor"

    def yonergeler(p: str) -> set[str]:
        return {" ".join(k.split()) for k in p.split(";") if k.strip()}

    assert yonergeler(CSP_SPA) == yonergeler(m.group(1)), (
        f"Uygulama ve nginx CSP'si ayrışmış.\n  Yalnız uygulamada: "
        f"{sorted(yonergeler(CSP_SPA) - yonergeler(m.group(1)))}\n  Yalnız nginx'te: "
        f"{sorted(yonergeler(m.group(1)) - yonergeler(CSP_SPA))}"
    )


def test_index_html_INLINE_script_TASIMAZ():
    """`script-src 'self'` inline script'i engeller — sessizce.

    Tema başlatıcı inline duruyordu: sayfa açılır ama tema yanlış başlar ve konsolda bir
    CSP ihlali kalır. Çözüm CSP'yi 'unsafe-inline' ile gevşetmek DEĞİL, kodu kurallara
    uygun yere taşımaktı (L51) — `frontend/public/theme-init.js`.
    """
    import re
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent.parent
    html = (kok / "frontend" / "index.html").read_text(encoding="utf-8")
    inline = [m for m in re.finditer(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", html, re.S)
              if m.group(1).strip()]
    assert not inline, (
        f"index.html'de {len(inline)} inline script var — CSP bunları engeller. "
        "Harici dosyaya taşıyın (frontend/public/)."
    )
