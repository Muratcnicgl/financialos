"""
P2 (Wave-9) — BUG #185: OAuth state deposu process-yereldi + PKCE yoktu.

(a) `_states` bir Python sözlüğüydü. gunicorn `--workers 2+` ile /login isteği worker-A'da,
    callback worker-B'de işlenirse `consume_state` BAŞARISIZ olur → OAuth girişleri kabaca
    %50 oranında "Geçersiz state" verir. Bu hem işlevsel bir bozukluk hem de operatörü
    CSRF korumasını gevşetmeye iten bir baskıdır. Ayrıca restart tüm akışları düşürür.

(b) PKCE yoktu: authorization code redirect zincirinde yakalanırsa (log/geçmiş/kötü niyetli
    uzantı) kod yeniden kullanılabilir. Gizli-istemci akışı olduğu için sömürü client_secret
    gerektirir; yine de PKCE modern OAuth'ta taban gerekliliktir (RFC 9700).

Çözüm: state artık imzalı, 10 dk ömürlü, TEK KULLANIMLIK bir token (jti kara listesi) →
tüm worker'lar doğrular. PKCE verifier'ı httpOnly çerezde taşınır (state içinde DEĞİL —
state tarayıcı/sağlayıcı üzerinden geçtiği için verifier orada açık olurdu).
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
from app.services import oauth as _oauth


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-oauth-state-pkce-0123456789abcdef")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    from app import rate_limit
    rate_limit.reset()


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(name="oauth", email="o@example.com", is_active=True))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ── (a) state stateless + tek kullanımlık ───────────────────────────────────

def test_state_process_yerel_sozlukte_tutulmaz(db):
    """Farklı 'worker' (temiz modül durumu) üretilen state'i doğrulayabilmeli."""
    state = _oauth.new_state()
    _oauth._states.clear()           # worker-B'nin belleği: state'i hiç görmedi
    assert _oauth.consume_state(state, db) is True, (
        "State process-yerel bellekte tutuluyor — çok-worker'da OAuth girişleri düşer"
    )


def test_state_tek_kullanimlik(db):
    state = _oauth.new_state()
    assert _oauth.consume_state(state, db) is True
    assert _oauth.consume_state(state, db) is False, "State tekrar kullanılabildi (CSRF/replay)"


def test_uydurma_state_reddedilir(db):
    assert _oauth.consume_state("uydurma-state-degeri", db) is False


def test_baska_tur_token_state_olarak_gecmez(db):
    """Tip karışıklığı: access token state yerine kullanılamamalı."""
    from app import auth as _auth
    assert _oauth.consume_state(_auth.create_access_token(1), db) is False


# ── (b) PKCE ────────────────────────────────────────────────────────────────

def test_google_yetkilendirme_urlinde_pkce_var():
    verifier = _oauth.new_code_verifier()
    url = _oauth.get_auth_url("google", "state123", code_verifier=verifier)
    assert "code_challenge=" in url and "code_challenge_method=S256" in url, (
        f"PKCE parametreleri yok: {url[:200]}"
    )


def test_login_pkce_cerezi_birakir(client):
    """Verifier httpOnly çerezde taşınır (state içinde DEĞİL — state sağlayıcıya gider)."""
    r = client.get("/api/auth/oauth/google/login", follow_redirects=False)
    assert r.status_code == 307, r.text[:200]
    cerez = r.headers.get("set-cookie", "")
    assert "fos_pkce=" in cerez, f"PKCE çerezi bırakılmadı: {cerez[:160]}"
    assert "httponly" in cerez.lower(), "PKCE çerezi httpOnly değil (JS okuyabilir)"
    # Verifier yönlendirme URL'inde ASLA görünmemeli
    konum = r.headers.get("location", "")
    assert "code_verifier" not in konum, "Verifier yetkilendirme URL'ine sızdı"
