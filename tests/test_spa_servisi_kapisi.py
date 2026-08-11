"""
B4 / BUG #284 — nginx'siz kurulumda SPA'yı uygulama servis eder.

Kapalı betanın ilk adımı Docker'sız koşuluyor (makinede Docker/WSL yok — ÖLÇÜLDÜ) ve tünel
TEK bir yerel porta vekillik eder. nginx yokken o portta hem `/api/*` hem de derlenmiş
arayüz bulunmalı; aksi hâlde davetli **boş sayfa** görür.

Kilitlenen dört sözleşme:
  1. **Varsayılan KAPALI** — Docker/nginx yolu değişmez (iki katman aynı işi yapmaz).
  2. **Açıkken /api gölgelenmez** — catch-all mount API'yi yutarsa TÜM uygulama ölür.
     Bu kapının asıl işi budur: mount yanlış yere taşınırsa burası kırmızıya döner.
  3. **Fail-fast** — `SERVE_SPA=1` ama build yoksa açılışta patlar; sessizce 404 servis
     etmek operatöre "kurdum" dedirtir, davetliye boş sayfa gösterir (L2/L5).
  4. **Kök yol SPA modunda uygulamayı döndürür**, sağlık JSON'unu değil.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.spa import dist_yolu, index_dosyasi, spa_aktif, spa_kur


@pytest.fixture(autouse=True)
def _temiz_env(monkeypatch):
    monkeypatch.delenv("SERVE_SPA", raising=False)
    monkeypatch.delenv("SPA_DIST", raising=False)


# ── 1. Varsayılan kapalı ────────────────────────────────────────────────

def test_varsayilan_KAPALI():
    """Env verilmezse nginx yolu aynen çalışır — yeni kod hiçbir şeye dokunmaz."""
    assert spa_aktif() is False
    assert spa_kur(FastAPI()) is False


@pytest.mark.parametrize("deger,beklenen", [
    ("1", True), ("true", True), ("TRUE", True), ("yes", True),
    ("0", False), ("false", False), ("", False), ("hayir", False),
])
def test_bayrak_okumasi(monkeypatch, deger, beklenen):
    monkeypatch.setenv("SERVE_SPA", deger)
    assert spa_aktif() is beklenen


# ── 2. Açıkken /api GÖLGELENMEZ (bu kapının asıl işi) ───────────────────

def _sahte_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>FinancialOS</body></html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "manifest.webmanifest").write_text('{"name":"FinancialOS"}', encoding="utf-8")
    return dist


def test_mount_API_yollarini_GOLGELEMEZ(monkeypatch, tmp_path):
    """Catch-all mount /api'den ÖNCE eklenirse tüm API 404 olur — sessiz ve ölümcül."""
    monkeypatch.setenv("SERVE_SPA", "1")
    monkeypatch.setenv("SPA_DIST", str(_sahte_dist(tmp_path)))

    app = FastAPI()

    @app.get("/api/ornek")
    def ornek():
        return {"ok": True}

    assert spa_kur(app) is True          # mount, route'lardan SONRA
    c = TestClient(app)
    r = c.get("/api/ornek")
    assert r.status_code == 200, "SPA mount API yolunu yutmuş"
    assert r.json() == {"ok": True}


def test_gercek_uygulamada_api_uclari_ayakta(monkeypatch, tmp_path):
    """Üretim `app` nesnesiyle uçtan uca: mount main.py'nin SONUNDA olmalı."""
    monkeypatch.setenv("SERVE_SPA", "1")
    monkeypatch.setenv("SPA_DIST", str(_sahte_dist(tmp_path)))
    from app.main import app as gercek_app

    # Üretim app'i import anında (SERVE_SPA kapalıyken) kurulduğu için mount yok;
    # burada mount'u ekleyip API'nin hâlâ cevap verdiğini ölçüyoruz.
    eklendi = spa_kur(gercek_app)
    try:
        assert eklendi is True
        c = TestClient(gercek_app)
        assert c.get("/api/health").status_code == 200, "SPA mount /api/health'i yutmuş"
        assert c.get("/api/meta").status_code == 200, "SPA mount /api/meta'yı yutmuş"
    finally:
        gercek_app.router.routes = [
            r for r in gercek_app.router.routes if getattr(r, "name", None) != "spa"
        ]
        gercek_app.openapi_schema = None


def test_statik_dosyalar_servis_edilir(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVE_SPA", "1")
    monkeypatch.setenv("SPA_DIST", str(_sahte_dist(tmp_path)))
    app = FastAPI()
    spa_kur(app)
    c = TestClient(app)
    assert c.get("/assets/app.js").status_code == 200
    # PWA'nın çalışması için manifest de servis edilmeli (ADR-040)
    assert c.get("/manifest.webmanifest").status_code == 200


# ── 3. Fail-fast ────────────────────────────────────────────────────────

def test_build_yoksa_ACILISTA_patlar(monkeypatch, tmp_path):
    """Sessizce 404 servis etmek yasak: operatör 'kurdum' sanır, davetli boş sayfa görür."""
    monkeypatch.setenv("SERVE_SPA", "1")
    monkeypatch.setenv("SPA_DIST", str(tmp_path / "olmayan"))
    with pytest.raises(RuntimeError) as e:
        spa_kur(FastAPI())
    assert "npm run build" in str(e.value), "Hata mesajı operatöre ÇÖZÜMÜ söylemiyor"


def test_hata_mesaji_aranan_yolu_soyler(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVE_SPA", "1")
    monkeypatch.setenv("SPA_DIST", str(tmp_path / "yok"))
    with pytest.raises(RuntimeError) as e:
        spa_kur(FastAPI())
    assert str(tmp_path / "yok") in str(e.value)


# ── 4. Kök yol ──────────────────────────────────────────────────────────

def test_kok_yol_SPA_modunda_uygulamayi_dondurur(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVE_SPA", "1")
    monkeypatch.setenv("SPA_DIST", str(_sahte_dist(tmp_path)))
    from app.main import app as gercek_app
    c = TestClient(gercek_app)
    r = c.get("/")
    assert r.status_code == 200
    assert "FinancialOS" in r.text
    assert "status" not in r.headers.get("content-type", ""), "kök hâlâ JSON döndürüyor"


def test_kok_yol_NORMAL_modda_saglik_JSON_u(monkeypatch):
    """SPA kapalıyken davranış AYNEN korunur (regresyon kilidi)."""
    monkeypatch.delenv("SERVE_SPA", raising=False)
    from app.main import app as gercek_app
    r = TestClient(gercek_app).get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_dist_yolu_varsayilani_repo_icinde():
    """SPA_DIST verilmezse repo'daki frontend/dist kullanılır."""
    yol = dist_yolu()
    assert yol.name == "dist" and yol.parent.name == "frontend"
    assert index_dosyasi() == yol / "index.html"
