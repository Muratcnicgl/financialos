"""
SEC-027 / BUG #436 KAPISI — CANLILIK UCU SÜRÜM/SHA/KİMLİK BİLGİSİ YAYINLAMAZ.

Ölçülen (12 Eyl 2026): kimliksiz `/api/health` `version`, `build` (commit SHA), `auth_enabled`
ve `service` döndürüyordu. Meşru okuyucular başka uçta: dağıtım kapısı `/api/meta.build`,
giriş ekranı `/api/meta.kimlik_gerekli`. Ayrıca istemcideki giriş kapısı var olmayan
`healthApi.get`i çağırıyordu → hiç çalışmıyor, giriş ekranına 401 dalgasıyla düşülüyordu
(`frontend/src/giris-kapisi.test.jsx`).

Kilitlenen: `/api/health` ve kök `/` (SPA kapalıyken) yalnız `status`; `/api/meta`
`kimlik_gerekli` taşır ve `auth_enabled()` ile aynıdır; `build` yalnız meta'da.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

YASAK = {"version", "build", "auth_enabled", "service", "surum"}


def test_canlilik_ucu_yalniz_status():
    govde = TestClient(app).get("/api/health").json()
    assert govde == {"status": "ok"}, govde
    assert not (set(govde) & YASAK)


def test_kok_yol_spa_kapaliyken_de_sizdirmaz(monkeypatch):
    monkeypatch.setattr("app.spa.spa_aktif", lambda: False)
    govde = TestClient(app).get("/").json()
    assert not (set(govde) & YASAK), govde


def test_kunye_kimlik_gerekli_tasir_ve_kaynakla_ayni(monkeypatch):
    c = TestClient(app)
    for deger in (True, False):
        monkeypatch.setattr("app.routers.meta.auth_enabled", lambda d=deger: d)
        govde = c.get("/api/meta").json()
        assert govde["kimlik_gerekli"] is deger
    assert "build" in govde and "surum" in govde
