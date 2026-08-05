"""
P2.9 / BUG #213 — istek gövdesi sınırı YALNIZ nginx'te vardı.

`deploy/nginx.conf.template` içindeki `client_max_body_size 1m` tek savunmaydı. Bu
üç durumda hiçbir koruma bırakmıyor: (1) uygulamaya ters vekil ATLANARAK erişilirse
(docker ağı, nginx'siz kurulum, yerel çalıştırma), (2) nginx yapılandırması sessizce
değişirse — uygulama tarafında bunu yakalayan test YOKTU, (3) chunked gövdede
`Content-Length` hiç gelmez, boyut ancak akarken sayılarak bilinir.

Bu dosya sınırı uygulama katmanında kilitler: dış yapılandırma ne olursa olsun
FastAPI 1 MiB üstü gövdeyi 413 ile reddeder ve bunu **beklenen bir reddetme** olarak
yapar (500 + hata-izleme kaydı DEĞİL).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.main import app
from app.request_limits import (
    VARSAYILAN_AZAMI_BAYT,
    GovdeBoyutuMiddleware,
    GovdeCokBuyuk,
    azami_govde_bayt,
)


# ── Birim: middleware'in kendisi ─────────────────────────────────────────────

@pytest.fixture
def mini_client():
    """Middleware'i izole ölçmek için minimal ASGI uygulaması."""
    async def _yut(request):
        govde = await request.body()
        return JSONResponse({"bayt": len(govde)})

    async def _govde_hatasi(request, exc: GovdeCokBuyuk):
        return JSONResponse({"detail": "cok buyuk"}, status_code=413)

    mini = Starlette(
        routes=[Route("/yut", _yut, methods=["POST"])],
        exception_handlers={GovdeCokBuyuk: _govde_hatasi},
    )
    mini.add_middleware(GovdeBoyutuMiddleware)
    return TestClient(mini)


def test_sinir_altindaki_govde_gecer(mini_client):
    r = mini_client.post("/yut", content=b"x" * 1000)
    assert r.status_code == 200 and r.json()["bayt"] == 1000


def test_content_length_ile_buyuk_govde_413(mini_client, monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "2048")
    r = mini_client.post("/yut", content=b"x" * 5000)
    assert r.status_code == 413, "Sınırı aşan gövde kabul edildi"


def test_chunked_govde_de_kesilir(mini_client, monkeypatch):
    """Content-Length YOKKEN de korunmalı — yoksa sınır tek başlıkla atlanır."""
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "2048")

    def _akit():
        for _ in range(50):
            yield b"x" * 1000

    r = mini_client.post("/yut", content=_akit())
    assert r.status_code == 413, "Chunked gövde sınırı atlıyor (Content-Length gelmez)"


def test_govde_tamamen_okunmadan_reddedilir(mini_client, monkeypatch):
    """Content-Length yolunda uygulama HİÇ çalışmamalı (ucuz reddetme)."""
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "1024")
    r = mini_client.post("/yut", content=b"x" * 4096)
    assert r.status_code == 413
    assert "bayt" not in r.json(), "Endpoint çalıştı — gövde boşuna okundu"


# ── Sınırın kendisi: yapılandırma güvenliği ──────────────────────────────────

def test_varsayilan_sinir_nginx_ile_ayni():
    """İki katman aynı sözü vermeli; aksi halde biri diğerini yalanlar."""
    assert VARSAYILAN_AZAMI_BAYT == 1024 * 1024


def test_nginx_sablonu_ayni_siniri_soyluyor():
    """nginx sessizce gevşetilirse bu test kırılır (yapılandırma drift kilidi)."""
    from pathlib import Path
    metin = Path("deploy/nginx.conf.template").read_text(encoding="utf-8")
    assert "client_max_body_size 1m;" in metin, \
        "nginx gövde sınırı değişti — app katmanıyla uyumu gözden geçir"


@pytest.mark.parametrize("ham", ["", "abc", "0", "-5"])
def test_gecersiz_env_varsayilana_duser(monkeypatch, ham):
    """Yanlış env değeriyle koruma SESSİZCE ÖLMEMELİ (sınırsız'a kaçış yok)."""
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", ham)
    assert azami_govde_bayt() == VARSAYILAN_AZAMI_BAYT


def test_env_ile_daraltilabilir(monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "4096")
    assert azami_govde_bayt() == 4096


# ── Bütünleşik: gerçek uygulama ──────────────────────────────────────────────

def test_gercek_uygulamada_kurulu(monkeypatch):
    """Middleware app'e BAĞLI mı — birim testi geçip üretimde devre dışı kalmasın."""
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "2048")
    c = TestClient(app)
    r = c.post("/api/coach/chat", content=b"x" * 8192,
               headers={"Content-Type": "application/json"})
    assert r.status_code == 413, f"Uygulama büyük gövdeyi kabul etti: {r.status_code}"


def test_413_hata_izlemeye_dusmez(monkeypatch):
    """Beklenen reddetme, "beklenmedik hata" tablosunu şişirmemeli (triyaj gürültüsü)."""
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "2048")
    cagrildi = []
    import app.error_tracking as et
    monkeypatch.setattr(et, "kaydet", lambda *a, **k: cagrildi.append(1))

    c = TestClient(app)
    r = c.post("/api/coach/chat", content=b"x" * 8192,
               headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert not cagrildi, "413 hata izlemeye yazıldı — operatör triyajı gürültüyle dolar"


def test_normal_istek_etkilenmez():
    """Sınır gerçek kullanımı bozmamalı — künye ucu çalışmaya devam etmeli."""
    c = TestClient(app)
    assert c.get("/api/meta").status_code == 200
