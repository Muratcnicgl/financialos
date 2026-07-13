"""
W3-040 (SEC-003/MN-002) — CORS güvenlik testleri.

CORS origin'leri env-driven (CORS_ORIGINS), methods/headers wildcard değil açık liste.
allow_credentials=True olduğundan wildcard origin CORS spec'inde zaten yasak; burada
izinli/izinsiz origin ayrımı + wildcard-method olmadığı doğrulanır.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _preflight(origin: str):
    return client.options(
        "/api/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_cors_izinli_origin_yansitilir():
    r = _preflight("http://localhost:5173")
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_bilinmeyen_origin_reddedilir():
    r = _preflight("https://evil.example.com")
    # İzinsiz origin CORS başlığı almamalı (tarayıcı isteği bloklar).
    assert r.headers.get("access-control-allow-origin") is None


def test_cors_methods_wildcard_degil():
    r = _preflight("http://localhost:5173")
    allow_methods = r.headers.get("access-control-allow-methods", "")
    assert "*" not in allow_methods
    assert "GET" in allow_methods and "POST" in allow_methods


# M22: _compute_cors_origins FRONTEND_URL birleştirme
def test_cors_origins_explicit(monkeypatch):
    from app.main import _compute_cors_origins
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com,https://b.com")
    assert _compute_cors_origins() == ["https://a.com", "https://b.com"]


def test_cors_origins_frontend_url_merge(monkeypatch):
    from app.main import _compute_cors_origins
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("FRONTEND_URL", "https://financialos.example.com/")
    origins = _compute_cors_origins()
    assert "https://financialos.example.com" in origins  # trailing slash temizlenir
    assert "http://localhost:5173" in origins  # dev default korunur


def test_cors_origins_default_only(monkeypatch):
    from app.main import _compute_cors_origins
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    assert "http://localhost:5173" in _compute_cors_origins()
