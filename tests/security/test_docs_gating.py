"""M34 (SEC-015) — /docs production'da kapalı, development'ta açık."""
from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app
from app.settings import is_production


def test_docs_dev_acik():
    # Test ortamı development (ENVIRONMENT set değil) → /docs erişilir
    assert is_production() is False
    c = TestClient(app)
    assert c.get("/docs").status_code == 200
    assert c.get("/openapi.json").status_code == 200


def test_app_docs_url_dev():
    # Dev'de docs_url tanımlı (prod'da None olurdu — is_production gate'i M16 testli)
    assert app.docs_url == "/docs" and app.openapi_url == "/openapi.json"
