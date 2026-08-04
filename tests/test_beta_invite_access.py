"""
P7 (Wave-9) — BUG #199: KAPALI BETA gerçekten kapalı olmalı.

`POST /api/auth/register` herkese açıktı. Sunucu canlıya çıktığı an bağlantıyı bilen
herkes hesap açabilirdi — "kapalı beta" bir İDDİA olurdu, kontrol değil. Finansal veri
taşıyan bir üründe davetli-dışı kayıt kabul edilemez (masterprompt §2 Basamak A).

Kilitlenen sözleşme: production'da varsayılan **davetli-only** (fail-closed), kod
tek kullanımlık, e-postaya bağlanabilir, süreli; ret sebebi sızdırılmaz.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base, BetaInvite, User
from app.beta_access import davet_olustur, registration_mode, invite_required


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-beta-invite-0123456789abcdef")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("REGISTRATION_MODE", raising=False)
    from app import rate_limit
    rate_limit.reset()


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _kayit(client, email="yeni@example.com", code=None):
    govde = {"email": email, "password": "Guclu-Parola-2026!", "name": "Yeni",
             "kvkk_consent": True}
    if code is not None:
        govde["invite_code"] = code
    return client.post("/api/auth/register", json=govde)


# ── Varsayılanlar: fail-closed ──────────────────────────────────────────────

def test_production_varsayilani_davetli_only(monkeypatch):
    """Operatör hiçbir şey yazmasa bile prod KAPALI olmalı (yanlış tarafa düşme)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert registration_mode() == "invite_only"
    assert invite_required() is True


def test_dev_varsayilani_acik(monkeypatch):
    """Geliştirme akışı bozulmaz."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert registration_mode() == "open"


# ── Kapalı modda davranış ───────────────────────────────────────────────────

def test_kodsuz_kayit_reddedilir(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    r = _kayit(client)
    assert r.status_code == 403, f"Kodsuz kayıt kabul edildi ({r.status_code}) — beta kapalı değil"


def test_gecersiz_kod_reddedilir(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    assert _kayit(client, code="uydurma-kod").status_code == 403


def test_gecerli_kodla_kayit_calisir(client, db, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    d = davet_olustur(db, note="test")
    r = _kayit(client, code=d.code)
    assert r.status_code == 201, r.text[:200]
    assert r.json()["access_token"]


def test_kod_tek_kullanimlik(client, db, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    d = davet_olustur(db)
    assert _kayit(client, email="bir@example.com", code=d.code).status_code == 201
    r2 = _kayit(client, email="iki@example.com", code=d.code)
    assert r2.status_code == 403, "Aynı davet kodu ikinci kez kullanıldı"


def test_epostaya_bagli_kod_baskasinda_calismaz(client, db, monkeypatch):
    """Kod paylaşılsa bile yalnız hedef adres kayıt olabilmeli."""
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    d = davet_olustur(db, email="hedef@example.com")
    assert _kayit(client, email="baskasi@example.com", code=d.code).status_code == 403
    assert _kayit(client, email="hedef@example.com", code=d.code).status_code == 201


def test_suresi_gecmis_kod_reddedilir(client, db, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    d = davet_olustur(db)
    d.expires_at = datetime.utcnow() - timedelta(days=1)
    db.commit()
    assert _kayit(client, code=d.code).status_code == 403


def test_ret_sebebi_sizdirilmaz(client, db, monkeypatch):
    """Kod deneme saldırısına 'kod var ama süresi geçmiş' gibi ipucu verilmez."""
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    d = davet_olustur(db, email="hedef@example.com")
    r1 = _kayit(client, email="baskasi@example.com", code=d.code)
    r2 = _kayit(client, email="baskasi@example.com", code="hic-olmayan")
    assert r1.json()["detail"] == r2.json()["detail"]


def test_kullanilan_kod_kime_gittigini_kaydeder(client, db, monkeypatch):
    """Operatör kimin hangi davetle girdiğini görebilmeli (beta takibi)."""
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    d = davet_olustur(db, note="Ali")
    _kayit(client, email="ali@example.com", code=d.code)
    db.refresh(d)
    kullanici = db.query(User).filter(User.email == "ali@example.com").first()
    assert d.used_at is not None and d.used_by_user_id == kullanici.id


# ── Açık modda regresyon ────────────────────────────────────────────────────

def test_acik_modda_kod_gerekmez(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "open")
    assert _kayit(client).status_code == 201
