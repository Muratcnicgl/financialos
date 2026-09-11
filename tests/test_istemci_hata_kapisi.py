"""
OBS-013 / BUG #406 KAPISI — TARAYICI HATALARI SUNUCU DEFTERİNE DÜŞER.

Ölçülen (12 Eyl 2026): `error_logs` yalnız sunucu istisnalarını tutuyordu; tarayıcıda çöken
panel kullanıcının konsolunda kalıyordu (ErrorBoundary `console.error`). Operatör "davetli
neyi görmüş?" sorusuna cevap veremiyordu.

Kilitlenen: `POST /api/ops/istemci-hata` kimlikli, IP başına 30/dk; aynı parmak izi
(tip + yol + yığının ilk çerçeveleri, mesaj HARİÇ) tek satırda birleşir ve sayacı artar;
mesaj/yığın maskeden geçer; kimliksiz istek 401.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import rate_limit
from app.dependencies import get_current_user, get_db
from app.error_tracking import istemci_parmak_izi, kaydet_istemci
from app.main import app
from app.models import Base, ErrorLog, User


@pytest.fixture
def ortam():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="u")); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    rate_limit.reset()
    try:
        yield s, TestClient(app)
    finally:
        app.dependency_overrides.clear(); rate_limit.reset(); s.close()


def test_parmak_izi_mesaji_disarida_tutar_yigini_icerir():
    a = istemci_parmak_izi("TypeError", "panel:cockpit", "at f (a.js:1:2)\nat g (b.js:3:4)")
    b = istemci_parmak_izi("TypeError", "panel:cockpit", "at f (a.js:1:2)\nat g (b.js:3:4)")
    c = istemci_parmak_izi("TypeError", "panel:cockpit", "at h (z.js:9:9)")
    assert a == b and a != c


def test_kaydet_birlestirir_ve_sayar(ortam):
    s, _ = ortam
    k1 = kaydet_istemci(s, tip="TypeError", mesaj="x is undefined (id=5)", yol="panel:cockpit",
                        yigin="at f (a.js:1:2)", user_id=1, istek_id="abc12345")
    k2 = kaydet_istemci(s, tip="TypeError", mesaj="x is undefined (id=9)", yol="panel:cockpit",
                        yigin="at f (a.js:1:2)", user_id=1, istek_id="def67890")
    assert k1 == k2
    kayit = s.get(ErrorLog, k1)
    assert kayit.occurrence_count == 2 and kayit.error_type == "istemci:TypeError"
    assert kayit.path == "istemci:panel:cockpit" and kayit.method == "JS"
    assert kayit.last_istek_id == "def67890"


def test_uc_202_doner_ve_defter_yazar(ortam):
    s, c = ortam
    r = c.post("/api/ops/istemci-hata", json={"tip": "RangeError", "mesaj": "red", "yigin": "at x (y.js:1:1)", "yol": "#coach"})
    assert r.status_code == 202, r.text
    assert r.json()["kayit_id"] is not None
    assert s.query(ErrorLog).count() == 1
    assert c.post("/api/ops/istemci-hata", json={"tip": "RangeError", "yigin": "at x (y.js:1:1)", "yol": "#coach"}).status_code == 202
    assert s.query(ErrorLog).count() == 1 and s.query(ErrorLog).first().occurrence_count == 2


def test_govde_sinirlari_422(ortam):
    _, c = ortam
    assert c.post("/api/ops/istemci-hata", json={"tip": "x" * 61}).status_code == 422
    assert c.post("/api/ops/istemci-hata", json={"yigin": "x" * 4001}).status_code == 422


def test_ip_basina_hiz_siniri(ortam):
    _, c = ortam
    max_r, _ = rate_limit.limit_for("istemci_hata")
    kodlar = [c.post("/api/ops/istemci-hata", json={"tip": "E", "yigin": f"f{i}"}).status_code for i in range(max_r)]
    assert 429 not in kodlar
    assert c.post("/api/ops/istemci-hata", json={"tip": "E", "yigin": "son"}).status_code == 429


def test_kimliksiz_401(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    app.dependency_overrides.clear()
    r = TestClient(app).post("/api/ops/istemci-hata", json={"tip": "E"})
    assert r.status_code == 401
