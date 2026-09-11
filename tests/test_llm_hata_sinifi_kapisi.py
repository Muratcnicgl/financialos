"""
LLM-038 / BUG #409 KAPISI — KOÇ DÜŞTÜĞÜNDE "NEDEN" YAPISAL.

Ölçülen (12 Eyl 2026): iki düşme yolu (router except'i, motorun "tüm sağlayıcılar denendi"
dalı) tek düz cümle dönüyordu; ham istisna yalnız logda (doğru, BE-009) ama sınıfı da
dışarı çıkmıyordu — istemci, izleme ve eval "kota mı, ağ mı?" ayıramıyordu.

Kilitlenen: `hata_sinifi` kapalı küme {kota, ag, saglayici, bilinmeyen}; tip+mesaj
sinyalinden sınıflanır; kullanıcı mesajı sınıfa göre, ham mesaj dışarı ÇIKMAZ; her iki
yol da alanı taşır; başarılı cevapta None.
"""
from __future__ import annotations

import pytest

from app import llm_hata


class _RateLimitError(Exception): ...


@pytest.mark.parametrize("hata, beklenen", [
    # Sınıflar provider_errors'tan (BUG #269): kod YAPIDAN, metinde sayı yok
    (RuntimeError("Error code: 429 - {'error': {'message': 'Rate limit reached'}}"), "kota"),
    (RuntimeError("RESOURCE_EXHAUSTED: quota exceeded"), "kota"),
    (RuntimeError("402 payment required"), "kota"),
    (RuntimeError("Request timed out"), "gecici"),
    (RuntimeError("Error code: 503 - overloaded"), "gecici"),
    (RuntimeError("Error code: 413 - Limit 8000, Requested 8429"), "istek_cok_buyuk"),
    (RuntimeError("Latency budget exceeded: upstream took 4290 ms"), "bilinmeyen"),   # 4290 ≠ 429; kod yok → bilinmeyen
    (RuntimeError("SECRET-INTERNAL-DETAIL stack xyz"), "bilinmeyen"),
    (RuntimeError("Error code: 400 - invalid request"), "kalici"),
    (None, "bilinmeyen"),
])
def test_siniflandirma(hata, beklenen):
    assert llm_hata.hata_sinifi(hata) == beklenen


def test_kapali_kume_ve_her_sinifin_mesaji_var():
    assert set(llm_hata.SINIFLAR) == set(llm_hata.MESAJLAR)
    for s in llm_hata.SINIFLAR:
        m = llm_hata.kullanici_mesaji(s)
        assert len(m) > 40 and ("tekrar" in m or "bildir" in m)
    assert llm_hata.kullanici_mesaji("yok") == llm_hata.MESAJLAR["bilinmeyen"]


def test_tek_kaynak_provider_errors():
    """Sınıflandırma burada YENİDEN yazılmaz — BUG #269'un ölçülmüş sınıflandırıcısı kullanılır."""
    import inspect
    kaynak = inspect.getsource(llm_hata)
    assert "provider_errors" in kaynak and "re.compile" not in kaynak


def test_ham_istisna_mesaja_sizmaz():
    for s in llm_hata.SINIFLAR:
        m = llm_hata.kullanici_mesaji(s)
        assert "Traceback" not in m and "Error code" not in m


def test_router_dusme_yolu_sinifi_tasir(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.dependencies import get_current_user, get_db
    from app.main import app
    from app.models import Base, User
    from app.routers import coach as coach_router

    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)(); s.add(User(id=1, name="u")); s.commit()

    class _Motor:
        provider = None
        provider_name = "ScriptedProvider"
        model = "scripted-1"

        def chat(self, **k):
            raise _RateLimitError("Error code: 429 - rate limit reached")
    monkeypatch.setattr(coach_router, "_get_engine", lambda: _Motor())
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        r = TestClient(app).post("/api/coach/chat", json={"message": "durum"})
    finally:
        app.dependency_overrides.clear(); s.close()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["llm_kullanilamadi"] is True and body["hata_sinifi"] == "kota"
    assert "429" not in body["reply"] and "kota" in body["reply"].lower()
