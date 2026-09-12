"""
SEC-030 / BUG #435 KAPISI — SOHBET YANITINDAKİ KOKPİT KOPYASI İSTEMCİNİN OKUDUĞU KADAR.

Ölçülen (12 Eyl 2026): `/api/coach/chat` motorun kokpit dict'ini olduğu gibi yayınlıyordu:
tüm bakiyeler, uyarılar, alacak karşı tarafları, `_coach_extra_numbers` gibi iç alanlar.
İstemci yalnız `cockpit_snapshot.accounts[].id/ad` okuyor (PendingActions hesap adı çevirisi).
Tam kokpit `/api/cockpit`'te; sohbet yanıtında ikinci kez yayınlanması OWASP API3 fazlalığıydı.

Kilitlenen: yanıttaki snapshot yalnız `accounts` taşır, her hesap yalnız id/ad/tip; None geçer;
motorun kendi dict'i değişmez (daraltma API sınırında).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Base, User
from app.routers.coach import SNAPSHOT_HESAP_ALANLARI, _snapshot_daralt

TAM = {
    "nakit_kasa": 4276.0, "kart_borcu": 12000.0, "alerts": [{"kod": "x"}],
    "upcoming_receivables": [{"kim": "gizli kişi", "tutar": 500}],
    "_coach_extra_numbers": [1, 2],
    "accounts": [{"id": 1, "ad": "Nakit", "tip": "cash", "bakiye": 4276.0, "is_emanet": False, "limit": 0}],
}


@pytest.fixture
def client():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)(); s.add(User(id=1, name="u")); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear(); s.close()


class _Engine:
    provider_name = "ScriptedProvider"; model = "scripted-1"
    def __init__(self): self.verilen = dict(TAM)
    def chat(self, **kw):
        return {"reply": "ok", "proposed_actions": [], "cockpit_snapshot": self.verilen, "grounding": {"ok": True}}


def test_daraltma_saf():
    d = _snapshot_daralt(TAM)
    assert set(d) == {"accounts"}
    assert d["accounts"] == [{"id": 1, "ad": "Nakit", "tip": "cash"}]
    assert set(SNAPSHOT_HESAP_ALANLARI) == {"id", "ad", "tip"}
    assert _snapshot_daralt(None) is None and _snapshot_daralt({}) is None


def test_uc_yalniz_hesap_kimliklerini_yayinlar(client, monkeypatch):
    motor = _Engine()
    monkeypatch.setattr("app.routers.coach._get_engine", lambda: motor)
    r = client.post("/api/coach/chat", json={"message": "durum", "include_cockpit": True})
    assert r.status_code == 200, r.text[:200]
    snap = r.json()["cockpit_snapshot"]
    assert snap == {"accounts": [{"id": 1, "ad": "Nakit", "tip": "cash"}]}
    govde = r.text
    for sizmamali in ("nakit_kasa", "gizli kişi", "_coach_extra_numbers", "is_emanet", "12000"):
        assert sizmamali not in govde, f"sohbet yanıtına sızdı: {sizmamali}"
    assert motor.verilen is not None and "nakit_kasa" in motor.verilen, "motorun dict'i daraltılmaz"
