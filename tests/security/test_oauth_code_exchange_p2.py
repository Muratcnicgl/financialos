"""
P2 (Wave-9) — BUG #179: OAuth callback access + refresh token'ı URL'de taşıyordu.

Eski akış: backend `FRONTEND_URL/auth/oauth-success?access_token=..&refresh_token=..`
adresine 307 yapıyordu. 30 GÜNLÜK refresh token böylece tarayıcı geçmişine, nginx/gunicorn
access log'una, ara proxy loglarına ve sayfadan çıkılan her dış bağlantının `Referer`
başlığına yazılıyordu. Logları okuyan veya cihazı paylaşan biri 30 gün hesap erişimi kazanır.

Yeni akış (endüstri standardı, tek-kullanımlık değişim kodu):
  1. Callback → `?code=<60 sn ömürlü, tek-kullanımlık JWT>` ile yönlendirir.
  2. Frontend `POST /api/auth/oauth/exchange {code}` çağırır; token'lar YANIT GÖVDESİNDE gelir.
  3. Kod tek kullanımlıktır (jti kara listeye yazılır) ve 60 saniyede söner.

Kod stateless JWT'dir → çok-worker/çok-instance kurulumda da çalışır (process-yerel
sözlük gerekmez).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base, User


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-oauth-exchange-0123456789abcdef")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    from app import rate_limit
    rate_limit.reset()


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    u = User(name="oauth kullanıcı", email="oauth@example.com", is_active=True)
    s.add(u)
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_degisim_kodu_token_verir(client, db):
    from app import auth as _auth
    user = db.query(User).first()
    code = _auth.create_oauth_exchange_code(user.id)

    r = client.post("/api/auth/oauth/exchange", json={"code": code})
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert body["access_token"] and body["refresh_token"]

    # Token gerçekten çalışıyor
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert r.status_code == 200


def test_degisim_kodu_tek_kullanimlik(client, db):
    from app import auth as _auth
    user = db.query(User).first()
    code = _auth.create_oauth_exchange_code(user.id)

    assert client.post("/api/auth/oauth/exchange", json={"code": code}).status_code == 200
    r2 = client.post("/api/auth/oauth/exchange", json={"code": code})
    assert r2.status_code == 401, (
        f"Değişim kodu ikinci kez kullanılabildi ({r2.status_code}) — çalınan kod tekrar oynatılır"
    )


def test_gecersiz_kod_reddedilir(client):
    r = client.post("/api/auth/oauth/exchange", json={"code": "uydurma.kod.degeri"})
    assert r.status_code == 401


def test_access_tokeni_degisim_kodu_yerine_kullanilamaz(client, db):
    """Tip karışıklığı savunması: normal access token 'code' olarak geçerli olmamalı."""
    from app import auth as _auth
    user = db.query(User).first()
    access = _auth.create_access_token(user.id)
    r = client.post("/api/auth/oauth/exchange", json={"code": access})
    assert r.status_code == 401


def test_callback_urlde_token_tasimaz(client, db, monkeypatch):
    """Yönlendirme adresinde access/refresh token GEÇMEMELİ (log/geçmiş/Referer sızıntısı)."""
    import app.routers.auth as auth_mod

    user = db.query(User).first()
    monkeypatch.setattr(auth_mod._oauth, "consume_state", lambda s: True)
    monkeypatch.setattr(auth_mod._oauth, "exchange_code",
                        lambda provider, code: {"email": user.email, "sub": "123",
                                                "provider": "google",
                                                "name": "oauth kullanıcı"})

    r = client.get("/api/auth/callback/google?code=abc&state=xyz", follow_redirects=False)
    assert r.status_code in (302, 307), r.text[:200]
    konum = r.headers.get("location", "")
    assert "access_token=" not in konum and "refresh_token=" not in konum, (
        f"Token yönlendirme URL'inde taşınıyor: {konum[:160]}"
    )
    assert "code=" in konum, f"Değişim kodu yönlendirmede yok: {konum[:160]}"
