"""
BUG #238 (denetim D22) — uygulama RLS'i bypass eden bir DB rolüyle açılamaz.

NEDEN: prod compose uygulamayı postgres imajının `POSTGRES_USER`'ı ile bağlıyordu ve yorumu
"NON-superuser" diyordu. O rol bootstrap SUPERUSER'dır; superuser `FORCE ROW LEVEL SECURITY`'ye
rağmen her policy'yi bypass eder → ADR-038/M51'in "workspace izolasyonu DB-katmanı 2. savunma"
beyanı prod'da FİİLEN YOKTU. Rolün kimliği bağlantı dizesinden okunamaz (aynı ad farklı
cluster'da farklı yetkidedir) → tek doğrulama yolu çalışma anında sormaktır.

Statik tarafı `tests/test_prod_rls_rol_kapisi.py` ölçer (compose/CI sözleşmesi); burası
çalışma-anı fail-fast'ini ölçer.
"""
from __future__ import annotations

import pytest

from app.settings import database_role_problems, validate_security_config

_PG = "postgresql://fos_app:gizli@db:5432/financialos"


class _SahteSonuc:
    def __init__(self, super_, bypass):
        self.rolsuper, self.rolbypassrls = super_, bypass

    def one(self):
        return self


class _SahteBaglanti:
    def __init__(self, sonuc):
        self._sonuc = sonuc

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        if isinstance(self._sonuc, Exception):
            raise self._sonuc
        return self._sonuc


class _SahteEngine:
    def __init__(self, sonuc):
        self._sonuc = sonuc

    def connect(self):
        return _SahteBaglanti(self._sonuc)


def _rol_sonucu(monkeypatch, sonuc):
    import app.database
    monkeypatch.setattr(app.database, "engine", _SahteEngine(sonuc), raising=True)


@pytest.fixture
def prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", _PG)
    return monkeypatch


def test_superuser_rolu_problem_uretir(prod):
    _rol_sonucu(prod, _SahteSonuc(True, False))
    (sorun,) = database_role_problems()
    assert "bypass" in sorun and "superuser=True" in sorun


def test_bypassrls_rolu_de_problem_uretir(prod):
    """NOSUPERUSER ama BYPASSRLS bir rol savunmayı sessizce kaldırır — aynı kapıya takılmalı."""
    _rol_sonucu(prod, _SahteSonuc(False, True))
    assert database_role_problems(), "BYPASSRLS rolü fark edilmedi"


def test_normal_rol_temiz_gecer(prod):
    _rol_sonucu(prod, _SahteSonuc(False, False))
    assert database_role_problems() == []


def test_placeholder_sifre_reddedilir(prod):
    """MA3/BUG #157 sınıfı: git'teki `.env.prod.example` şifresiyle deploy edilemez."""
    # secret-ornek: sahte placeholder sifre (sir taramasi muafiyeti — SEC-018)
    prod.setenv("DATABASE_URL", "postgresql://fos_app:REPLACE_WITH_STRONG_APP_ROLE_PASSWORD@db/f")
    _rol_sonucu(prod, _SahteSonuc(False, False))
    assert any("placeholder" in s for s in database_role_problems())


def test_baglanti_kurulamazsa_bloklamaz(prod):
    """Asimetri: kanıtlanmış kötü durum kapatır, kanıtlanamayan durum crash-loop üretmez."""
    _rol_sonucu(prod, RuntimeError("connection refused"))
    assert database_role_problems() == []


def test_sqlite_self_host_etkilenmez(prod):
    """Hibrit dev/self-host (ADR-038): SQLite'ta RLS kavramı yok — kapı sessiz kalmalı."""
    prod.setenv("DATABASE_URL", "sqlite:///./data/financialos.db")
    _rol_sonucu(prod, _SahteSonuc(True, True))  # sorulmamalı bile
    assert database_role_problems() == []


def test_development_bloklanmaz(monkeypatch):
    """Yerel geliştirmede superuser postgres normaldir; kapı yalnız production'da konuşur."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", _PG)
    _rol_sonucu(monkeypatch, _SahteSonuc(True, True))
    assert database_role_problems() == []


def test_startup_fail_fast_zinciri_kapiya_bagli(prod):
    """Kapı `validate_security_config`'e gerçekten bağlı mı (yoksa kimse çağırmaz)."""
    prod.setenv("SECRET_KEY", "x" * 48)
    prod.setenv("AUTH_ENABLED", "true")
    prod.setenv("SUPPORT_EMAIL", "destek@ornek-urun.com")
    _rol_sonucu(prod, _SahteSonuc(True, False))
    with pytest.raises(RuntimeError, match="bypass"):
        validate_security_config()
