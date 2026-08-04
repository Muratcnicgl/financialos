"""
P3 (Wave-9) — BUG #188: kullanıcı-BAŞINA LLM tavanı yoktu.

Mevcut koruma `PROVIDER_DAILY_LIMITS` idi: sağlayıcının (Gemini free tier) GÜNLÜK KOTASI.
Bu bir maliyet/adalet guard'ı DEĞİL:

  - Kota tüm kullanıcılarca PAYLAŞILIR (tek API anahtarı). Kapalı betada tek kullanıcı
    günün kotasını tüketirse DİĞER HERKES koçu kullanamaz.
  - TPM-limitli sağlayıcılarda (`limit=0` dalı) hiçbir engel YOK → sınırsız çağrı.
  - Koç mesajı başına 2 LLM çağrısı yapılıyor (iki-geçiş mimarisi) → maliyet iki katı.

Ek olarak limit dolduğunda kullanıcıya gösterilen metin iç yapılandırma tavsiyesi
sızdırıyordu ("Anthropic'e gecis icin .env: LLM_PROVIDER=anthropic") — son kullanıcı için
anlamsız ve iç mimariyi ifşa eder.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, ApiCallLog, ApiCallStatus


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-coach-quota-0123456789abcdef")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "4")   # test için küçük tavan


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    a = User(name="a")
    b = User(name="b")
    s.add_all([a, b])
    s.commit()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _sahte_kocmotoru(monkeypatch):
    """Süit determinizmi: gerçek LLM çağrısı YAPILMAZ (ağ/kota/gecikme bağımlılığı yok)."""
    import app.routers.coach as coach_router

    class SahteMotor:
        provider_name = "FakeProvider"
        model = "fake-model"

        def chat(self, *a, **k):
            return {"reply": "Test cevabı.", "proposed_actions": [],
                    "cockpit_snapshot": None, "coach_memory_id": None}

    monkeypatch.setattr(coach_router, "_get_engine", lambda: SahteMotor())


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    state = {"user": db.query(User).filter(User.name == "a").first()}
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    c = TestClient(app)
    c._state = state
    yield c
    app.dependency_overrides.clear()


def _cagri_yaz(db, user_id: int, adet: int, saat_once: int = 0):
    """Kullanıcı adına ApiCallLog satırları üret (gerçek LLM çağrısı yapmadan)."""
    when = datetime.utcnow() - timedelta(hours=saat_once)
    for _ in range(adet):
        db.add(ApiCallLog(user_id=user_id, provider="gemini", model="test",
                          called_at=when, status=ApiCallStatus.success,
                          duration_ms=10, tool_calls_count=0))
    db.commit()


def test_kullanici_basina_tavan_uygulanir(client, db):
    """Tavan dolunca koç 429 döner (sağlayıcı kotası dolmamış olsa bile)."""
    a = db.query(User).filter(User.name == "a").first()
    _cagri_yaz(db, a.id, 4)          # COACH_DAILY_USER_LIMIT = 4

    r = client.post("/api/coach/chat", json={"message": "merhaba"})
    assert r.status_code == 429, f"Kullanıcı tavanı uygulanmadı ({r.status_code})"


def test_tavan_mesaji_ic_yapilandirma_sizdirmaz(client, db):
    a = db.query(User).filter(User.name == "a").first()
    _cagri_yaz(db, a.id, 4)
    r = client.post("/api/coach/chat", json={"message": "merhaba"})
    detay = str(r.json().get("detail", "")).lower()
    for jargon in (".env", "llm_provider", "anthropic", "gemini", "api key"):
        assert jargon not in detay, f"Kullanıcıya iç yapılandırma sızdı: {detay[:200]}"


def test_bir_kullanicinin_tuketimi_digerini_kilitlemez(client, db):
    """Adalet: A tavanını doldurunca B hâlâ koçu kullanabilmeli (paylaşılan kota tuzağı)."""
    a = db.query(User).filter(User.name == "a").first()
    b = db.query(User).filter(User.name == "b").first()
    _cagri_yaz(db, a.id, 10)

    client._state["user"] = b
    r = client.post("/api/coach/chat", json={"message": "merhaba"})
    assert r.status_code != 429, (
        "A'nın tüketimi B'yi kilitledi — kullanıcı-başına ayrım yok"
    )


def test_dunku_cagrilar_sayilmaz(client, db):
    """Pencere GÜNLÜK: dünkü çağrılar bugünün tavanını doldurmamalı."""
    a = db.query(User).filter(User.name == "a").first()
    _cagri_yaz(db, a.id, 10, saat_once=30)   # dün
    r = client.post("/api/coach/chat", json={"message": "merhaba"})
    assert r.status_code != 429, "Dünkü çağrılar bugünün tavanını dolduruyor"


def test_usage_ucu_kullanici_tavanini_gosterir(client, db):
    """Kullanıcı kendi kullanımını görebilmeli (şeffaflık + UI rozeti)."""
    a = db.query(User).filter(User.name == "a").first()
    _cagri_yaz(db, a.id, 2)
    r = client.get("/api/coach/usage")
    assert r.status_code == 200
    body = r.json()
    assert body.get("user_daily_limit") == 4, f"usage ucunda kullanıcı tavanı yok: {body}"
    assert body.get("user_today_count") == 2
