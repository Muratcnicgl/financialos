"""
BE-009: /api/coach/chat hata yönetimi — ham hata (str(e)) kullanıcıya SIZDIRILMAZ.
Graceful degradation (chat UX için 200) ama gerçek hata loglanır, kullanıcıya genel mesaj.
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


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


class _FailEngine:
    provider_name = "ScriptedProvider"
    model = "scripted-1"

    def chat(self, **kw):
        raise RuntimeError("SECRET-INTERNAL-DETAIL stack xyz")


def test_chat_hata_ham_detay_sizdirmaz(client, monkeypatch):
    monkeypatch.setattr("app.routers.coach._get_engine", lambda: _FailEngine())
    r = client.post("/api/coach/chat", json={"message": "selam", "include_cockpit": False})
    assert r.status_code == 200                      # graceful (chat UX)
    body = r.json()
    assert "SECRET-INTERNAL-DETAIL" not in body["reply"]   # ham hata sızmıyor
    assert "cevap veremedi" in body["reply"].lower()
    assert body["proposed_actions"] == []


def test_sec006_asiri_uzun_mesaj_422(client):
    """SEC-006: 4000 karakter üstü mesaj → 422 (sağlayıcı token/maliyet koruması)."""
    r = client.post("/api/coach/chat", json={"message": "x" * 4001, "include_cockpit": False})
    assert r.status_code == 422


def test_sec006_bos_mesaj_422(client):
    r = client.post("/api/coach/chat", json={"message": "", "include_cockpit": False})
    assert r.status_code == 422                       # min_length=1


class _DusenEngine:
    """Motor içeride yakaladı: özür metni + `llm_kullanilamadi` bayrağıyla döner (RESIL-004 yolu)."""
    provider_name = "ScriptedProvider"
    model = "scripted-1"

    def chat(self, **kw):
        return {"reply": "Koç (yapay zekâ yorumlayıcı) şu an ulaşılamıyor — panelindeki veriler güncel.",
                "proposed_actions": [], "cockpit_snapshot": None, "llm_kullanilamadi": True,
                "grounding": {"ok": True}}


class _CalisanEngine:
    provider_name = "ScriptedProvider"
    model = "scripted-1"

    def chat(self, **kw):
        return {"reply": "Nakit kasanda 4.276 TL var.", "proposed_actions": [],
                "cockpit_snapshot": None, "grounding": {"ok": True}}


def test_bug376_kocun_DUSTUGU_sozlesmede_gorunur(client, monkeypatch):
    """
    BUG #376 — API-004/BE-009/RESIL-016'nın kalan boşluğu. 200 bilinçli (sohbet UX) ama
    istemci "cevap" ile "özür metni"ni ayırt edemiyordu: motor `llm_kullanilamadi` üretiyor,
    `ChatResponse` alanı taşımıyordu. İKİ düşme yolu da bayrağı taşımalı.
    """
    monkeypatch.setattr("app.routers.coach._get_engine", lambda: _DusenEngine())
    r = client.post("/api/coach/chat", json={"message": "selam", "include_cockpit": False})
    assert r.status_code == 200
    assert r.json()["llm_kullanilamadi"] is True, "motorun bayrağı API'de kayboldu"

    monkeypatch.setattr("app.routers.coach._get_engine", lambda: _FailEngine())
    r = client.post("/api/coach/chat", json={"message": "selam", "include_cockpit": False})
    assert r.status_code == 200
    assert r.json()["llm_kullanilamadi"] is True, "router'ın kendi except yolu bayrak taşımıyor"


def test_bug376_koc_CALISINCA_bayrak_yanmaz(client, monkeypatch):
    """Gürültü tarafı: normal cevapta bayrak False — aksi hâlde istemci her cevapta uyarır."""
    monkeypatch.setattr("app.routers.coach._get_engine", lambda: _CalisanEngine())
    r = client.post("/api/coach/chat", json={"message": "selam", "include_cockpit": False})
    assert r.status_code == 200
    assert r.json()["llm_kullanilamadi"] is False
