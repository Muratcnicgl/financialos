"""
M16 (BUG #157) — SECRET_KEY startup fail-fast testleri.

Production'da eksik/dev-default/zayıf SECRET_KEY → RuntimeError (uygulama açılmaz).
Development'ta yalnız warning (çalışmaya devam). Güçlü SECRET_KEY → sorun yok.
"""
from __future__ import annotations

import pytest

from app.settings import validate_security_config, secret_key_problems, is_production

_GOOD = "x" * 48  # 48 char güçlü


def test_production_bos_secret_raise(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="FAIL-FAST"):
        validate_security_config()


def test_production_dev_default_raise(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "dev-default-insecure-key")
    with pytest.raises(RuntimeError, match="dev-default"):
        validate_security_config()


def test_production_kisa_secret_raise(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "kisa123")  # <32
    with pytest.raises(RuntimeError, match="entropy"):
        validate_security_config()


def test_production_guclu_secret_gecer(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", _GOOD)
    # BUG #171 (P2): production artık AUTH_ENABLED de şart koşuyor — bu test SECRET_KEY
    # kapısını ölçüyor, o yüzden diğer prod-şartı açıkça sağlanır.
    monkeypatch.setenv("AUTH_ENABLED", "true")
    # BUG #210 (P8): production destek kanalı da şart — bu test SECRET_KEY kapısını ölçer.
    monkeypatch.setenv("SUPPORT_EMAIL", "destek@ornek-urun.com")
    validate_security_config()  # raise ETMEZ


def test_development_bos_secret_raise_etmez(monkeypatch, caplog):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "")
    validate_security_config()  # dev → yalnız warning, raise yok
    assert is_production() is False


def test_secret_key_problems_tespit(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")
    assert any("tanımsız" in p or "boş" in p for p in secret_key_problems())
    monkeypatch.setenv("SECRET_KEY", _GOOD)
    assert secret_key_problems() == []
