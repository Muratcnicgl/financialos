"""
P2 (Wave-9) — BUG #182: rate limit iki yerden birden kırıktı.

(a) **Proxy arkasında tek kova:** limiter `request.client.host` kullanıyordu. Prod'da nginx
    ayrı konteynerden proxy'lediği için bu değer HER istekte nginx'in IP'siydi → tüm
    kullanıcılar aynı kovaya düşüyordu. Sonuç: bir saldırgan 5 hatalı login ile HERKESİN
    girişini 15 dakika kilitler (DoS), register'ı 3 istekle saatlerce kapatır; gerçek
    brute-force koruması ise anlamsızlaşır (kullanıcı ayrımı yok).

(b) **Çok-worker'da sayaç bölünmesi:** sayaçlar process-yerel sözlükteydi; gunicorn
    `--workers 2+` ile her worker kendi sayacını tutuyordu → ilan edilen 5/15dk pratikte
    worker sayısı kadar katlanıyordu. Ayrıca her deploy/restart sayaçları sıfırlıyordu.

Çözüm: (a) `TRUST_PROXY_HEADERS` açıkken X-Forwarded-For'un **en sağdaki** (bizim nginx'in
eklediği, istemcinin uyduramayacağı) değeri kullanılır. (b) sayaçlar DB'de tutulur —
tüm worker'lar aynı pencereyi görür, restart'ta sıfırlanmaz.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import rate_limit as rl
from app.dependencies import get_db
from app.models import Base


@pytest.fixture(autouse=True)
def _temiz(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    rl.reset()


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _app(db):
    """Rate-limit'i DB üzerinden uygulayan minik test app'i."""
    app = FastAPI()

    @app.get("/dene")
    def dene(request: Request, session=Depends(get_db)):
        rl.rate_limit(request, "login", db=session)
        return {"ok": True}

    app.dependency_overrides[get_db] = lambda: db
    return app


# ── (a) istemci IP çözümü ────────────────────────────────────────────────────

def test_proxy_guvenilmiyorken_forwarded_baslik_yok_sayilir(monkeypatch):
    """Varsayılan: X-Forwarded-For'a GÜVENİLMEZ (istemci uydurabilir)."""
    from starlette.requests import Request as SRequest
    scope = {"type": "http", "client": ("10.0.0.5", 1234),
             "headers": [(b"x-forwarded-for", b"1.2.3.4")]}
    assert rl.client_ip(SRequest(scope)) == "10.0.0.5"


def test_proxy_guvenilirken_en_sagdaki_deger_kullanilir(monkeypatch):
    """TRUST_PROXY_HEADERS=1: zincirin EN SAĞI bizim nginx'in eklediği gerçek peer'dır.

    En soldaki değer istemci tarafından uydurulabilir → kullanılmaz.
    """
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    from starlette.requests import Request as SRequest
    scope = {"type": "http", "client": ("172.18.0.3", 1234),
             "headers": [(b"x-forwarded-for", b"9.9.9.9, 203.0.113.7")]}
    assert rl.client_ip(SRequest(scope)) == "203.0.113.7"


def test_farkli_kullanicilar_birbirini_kilitlemez(monkeypatch, db):
    """(a) regresyon kilidi: A'nın denemeleri B'nin girişini engellememeli."""
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW", "900")
    c = TestClient(_app(db))

    for _ in range(3):
        assert c.get("/dene", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert c.get("/dene", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429, \
        "Saldırganın kendi limiti dolmadı"

    r = c.get("/dene", headers={"X-Forwarded-For": "2.2.2.2"})
    assert r.status_code == 200, (
        "Başka bir kullanıcı, saldırgan yüzünden kilitlendi — proxy arkasında tek kova"
    )


# ── (b) çok-worker: sayaç paylaşılır ────────────────────────────────────────

def test_sayac_db_de_paylasilir(monkeypatch, db):
    """İki ayrı 'worker' (iki app örneği, aynı DB) aynı pencereyi görmeli."""
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW", "900")
    worker_a = TestClient(_app(db))
    worker_b = TestClient(_app(db))
    h = {"X-Forwarded-For": "5.5.5.5"}

    assert worker_a.get("/dene", headers=h).status_code == 200
    assert worker_b.get("/dene", headers=h).status_code == 200
    assert worker_a.get("/dene", headers=h).status_code == 200
    # 4. istek — hangi worker'a giderse gitsin limit dolmuş olmalı
    assert worker_b.get("/dene", headers=h).status_code == 429, (
        "Sayaç worker'lar arasında paylaşılmıyor — limit worker sayısı kadar katlanıyor"
    )


def test_pencere_disindaki_kayitlar_temizlenir(monkeypatch, db):
    """Eski kayıtlar birikmemeli (sınırsız tablo büyümesi olmasın)."""
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_WINDOW", "1")
    c = TestClient(_app(db))
    h = {"X-Forwarded-For": "7.7.7.7"}
    assert c.get("/dene", headers=h).status_code == 200
    assert c.get("/dene", headers=h).status_code == 200
    assert c.get("/dene", headers=h).status_code == 429

    import time
    time.sleep(1.1)
    assert c.get("/dene", headers=h).status_code == 200, "Pencere geçtiği hâlde kilit sürüyor"

    from app.models import RateLimitHit
    kalan = db.query(RateLimitHit).count()
    assert kalan <= 2, f"Pencere dışı kayıtlar temizlenmiyor ({kalan} satır)"


def test_db_yoksa_bellek_yoluna_duser(monkeypatch):
    """Regresyon: DB verilmeyen çağrılar (dev/test) eskisi gibi çalışır."""
    from starlette.requests import Request as SRequest
    monkeypatch.setenv("RATE_LIMIT_LOGIN_MAX", "2")
    scope = {"type": "http", "client": ("10.0.0.9", 1), "headers": []}
    req = SRequest(scope)
    rl.rate_limit(req, "login")
    rl.rate_limit(req, "login")
    with pytest.raises(Exception):
        rl.rate_limit(req, "login")
