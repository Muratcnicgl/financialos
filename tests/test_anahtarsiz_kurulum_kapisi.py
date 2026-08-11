"""
ANAHTARSIZ KURULUM KAPISI — BUG #296.

ÖLÇÜLEN DEFEKT: LLM API anahtarı olmayan bir kurulumda `GET /api/coach/usage` **500**
veriyordu (`ValueError: GEMINI_API_KEY bulunamadi`). O uç Cockpit'in üst köşesindeki
"API kullanım" rozetini besler — yani anahtarı olmayan biri paneli hiç açamıyordu.

Kök neden bir katman karışıklığı: kullanım sayısı tamamen DB'den (`api_call_log`) gelir,
sağlayıcı yalnızca ETİKET için gerekir. Buna rağmen uç, cevap üretmeden önce **gerçek bir
sağlayıcı kurmaya** çalışıyordu. Yani bir SAYIYI göstermek için, o sayıyla ilgisi olmayan
bir dış servis bağlantısı ön koşuldu.

Nerede yakalandı: CI'da. Geliştirme makinesinde `.env` dolu olduğu için defekt yerelde
GÖRÜNMEZ — CI son 30 koşumdur kırmızıydı ve sebeplerinden biri buydu.

DERS (L58): bir uç, döndürdüğü veriden DAHA FAZLASINI ön koşul yapmamalı. "Sayıyı
göstermek için sağlayıcıyı kur" gibi gizli bağımlılıklar, o bağımlılığı olmayan her
kurulumda (yeni klon, self-host, CI, offline) ürünü çalışmaz kılar ve bunu geliştirme
makinesi asla göstermez.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User

# Sağlayıcı seçimini ve anahtarları etkileyen her değişken — hepsi BOŞ olmalı ki
# "hiç yapılandırılmamış kurulum" gerçekten test edilsin.
ANAHTARLAR = ("GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY",
              "OPENAI_API_KEY", "OLLAMA_ENABLED")


@pytest.fixture
def anahtarsiz(monkeypatch):
    for ad in ANAHTARLAR:
        monkeypatch.delenv(ad, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")   # yapılandırma var, ANAHTAR yok
    # Süreç ömrü boyunca yaşayan motor önbelleği sıfırlanır; aksi hâlde başka bir testin
    # kurduğu motor bu testi sahte-yeşil yapar.
    import app.routers.coach as coach_router
    monkeypatch.setattr(coach_router, "_engine", None)
    yield


@pytest.fixture
def client():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="anahtarsiz_kullanici"))
    s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    yield TestClient(app)
    app.dependency_overrides.clear()
    s.close()


def test_kullanim_rozeti_anahtarsiz_calisir(anahtarsiz, client):
    """KÖK DEFEKT: sayı DB'den gelir; sağlayıcı yokluğu bu ucu düşürmemeli."""
    r = client.get("/api/coach/usage")
    assert r.status_code == 200, (
        f"BUG #296: anahtarsız kurulumda kullanım rozeti {r.status_code} veriyor "
        f"→ Cockpit paneli açılmıyor. Gövde: {r.text[:200]}"
    )
    govde = r.json()
    assert "used" in govde or "count" in govde or govde, "kullanım bilgisi boş döndü"


def test_ic_hata_metni_disari_sizmaz(anahtarsiz, client):
    """BUG #175 ilkesi: sağlayıcı kurulamasa bile kullanıcı iç hata metni görmez."""
    govde = client.get("/api/coach/usage").text
    assert "GEMINI_API_KEY" not in govde
    assert "Traceback" not in govde
    assert ".env" not in govde


def test_okuma_uclari_anahtarsiz_ayakta(anahtarsiz, client):
    """Anahtar yokluğu YALNIZ koçu etkilemeli; paranın geri kalanı çalışmalı."""
    for yol in ("/api/cockpit", "/api/accounts", "/api/transactions", "/api/health"):
        r = client.get(yol)
        assert r.status_code < 500, f"{yol} anahtarsız kurulumda {r.status_code} verdi"
