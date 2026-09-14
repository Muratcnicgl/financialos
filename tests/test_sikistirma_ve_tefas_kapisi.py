"""
BUG #485: yanıt sıkıştırma (PERF-016) ve TEFAS URL tek kaynağı (FE-021).

Ölçüm (14 Eyl 2026): hiçbir yanıt gzip taşımıyordu; kokpit JSON'u ~40 KB, openapi.json
230 KB düz gidiyordu; tünel yolu (Tailscale/Cloudflare) uygulama katmanında sıkıştırmaz.
TEFAS URL'i iki panelde elle kuruluyordu; `fundPriceApi.tefasLink` istemcide hiç çağrılmıyordu.

Kilitlenen:
  1. ≥ 1 KB yanıt `Accept-Encoding: gzip` ile gzip döner ve gerçekten küçülür,
  2. küçük yanıt (sağlık) gzip başlığı taşımaz (eşik 1 KB — CPU'ya değmez),
  3. arayüz TEFAS URL'ini tek yardımcıdan alır; yardımcı backend `get_tefas_url` ile aynı
     dizeyi üretir (iki dil, tek gerçek); elle kurulmuş URL kalmadı; ölü istemci fonksiyonu yok.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.fund_tracker import get_tefas_url
from app.main import app

KOK = Path(__file__).resolve().parent.parent
FE = KOK / "frontend" / "src"


def test_buyuk_yanit_gzip_ile_kuculur():
    c = TestClient(app)
    duz = c.get("/openapi.json", headers={"Accept-Encoding": "identity"})
    assert duz.status_code == 200 and "content-encoding" not in duz.headers
    sikisik = c.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert sikisik.status_code == 200
    assert sikisik.headers.get("content-encoding") == "gzip", "≥1 KB yanıt gzip taşımıyor"
    # TestClient gövdeyi açar; sıkışık boyut `content-length` başlığında
    sikisik_boy = int(sikisik.headers["content-length"])
    assert sikisik_boy < len(duz.content) / 3, f"gzip küçültmüyor: {sikisik_boy} / {len(duz.content)}"
    assert sikisik.json() == duz.json()


def test_kucuk_yanit_gzip_tasimaz():
    c = TestClient(app)
    r = c.get("/api/health", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert "content-encoding" not in r.headers, "eşik altı yanıt sıkıştırılıyor (CPU israfı)"


def test_gzip_eşiği_kaynakta_1kb():
    src = (KOK / "app" / "main.py").read_text(encoding="utf-8")
    assert re.search(r"add_middleware\(GZipMiddleware, minimum_size=1024\)", src)


def test_tefas_url_tek_kaynak_ve_backendle_ayni():
    js = (FE / "lib" / "tefas.js").read_text(encoding="utf-8")
    m = re.search(r"return `(https://www\.tefas\.gov\.tr/FonAnaliz\.aspx\?FonKod=)\$\{String\(fundCode \|\| ''\)\.toUpperCase\(\)\}`", js)
    assert m, "tefas.js yardımcısı beklenen biçimde değil"
    assert get_tefas_url("tcd") == m.group(1) + "TCD", "backend ile arayüz farklı URL üretiyor"
    # elle kurulmuş URL kalmadı; iki panel de yardımcıyı kullanıyor
    kaynaklar = list((FE / "panels").glob("*.jsx")) + list((FE / "components").glob("*.jsx"))
    elle = [p.name for p in kaynaklar if "tefas.gov.tr" in p.read_text(encoding="utf-8")]
    assert elle == [], f"TEFAS URL'i elle kurulmuş: {elle}"
    kullanan = [p.name for p in kaynaklar if "tefasUrl(" in p.read_text(encoding="utf-8")]
    assert set(kullanan) >= {"Accounts.jsx", "Cockpit.jsx"}
    assert "tefasLink" not in (FE / "api.js").read_text(encoding="utf-8"), "ölü istemci fonksiyonu duruyor"
