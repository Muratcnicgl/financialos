"""
BUG #222 — şema sürümü kapısı.

Canlı kurulum kodun 9 migration gerisinde kalmıştı; uygulama yine de açılıyor, `/api/health`
yeşil dönüyordu. Kırıklık ancak kullanıcı koçtan bir aksiyonu onaylayınca ortaya çıkıyordu
(`master_checkpoints.rule_type` yok → 500). Kapı bunu startup'ta yakalamalı.

Kapının üç davranışı kilitlenir:
  1. `alembic_version` YOKSA (test/create_all yolu) sessiz geçer — geliştirme kilitlenmez (L6).
  2. Sürüm head ile aynıysa sessiz geçer.
  3. Sürüm geride/farklıysa: production'da RuntimeError, dev'de uyarı (sessiz KALMAZ).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.schema_guard import validate_schema_version, _kod_head


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                         poolclass=StaticPool)


def _surum_yaz(engine, surum: str):
    with engine.begin() as c:
        c.execute(text("create table alembic_version (version_num varchar(32) not null)"))
        c.execute(text("insert into alembic_version values (:v)"), {"v": surum})


def test_kod_head_okunabiliyor():
    """Kapının kendisi: beklenen head migration script'lerinden türetilebilmeli."""
    assert _kod_head(), "beklenen head okunamadı — kapı sessizce devre dışı kalır"


def test_alembic_version_yoksa_sessiz_gecer(engine):
    """Test/create_all yolu: in-memory DB'ler migration görmez, kapı karışmamalı."""
    assert validate_schema_version(engine) == "atlandi"


def test_guncel_surum_gecer(engine):
    _surum_yaz(engine, _kod_head())
    assert validate_schema_version(engine) == "guncel"


def test_geride_kalan_surum_productionda_uygulamayi_acmaz(engine, monkeypatch):
    """Asıl kanıt: 5 Ağustos'ta yaşanan durum production'da fail-fast olmalı."""
    _surum_yaz(engine, "a1b2c3d4e5f6")  # canlıda bulunan gerçek geride-kalmış sürüm
    monkeypatch.setattr("app.settings.is_production", lambda: True)
    with pytest.raises(RuntimeError, match="UYUŞMUYOR"):
        validate_schema_version(engine)


def test_geride_kalan_surum_devde_uyarir_ama_kilitlemez(engine, monkeypatch):
    """Dev'de açılış engellenmez ama uyumsuzluk SESSİZCE geçilmez.

    Sözleşme dönüş değeriyle sınanır, log'la değil: log'a dayanan ilk sürüm tam süitte
    (uygulama `basicConfig(force=True)` ile handler'ları değiştirdiğinde) kör kalıyordu —
    kapının kendi kör noktası olurdu (L3).
    """
    _surum_yaz(engine, "a1b2c3d4e5f6")
    monkeypatch.setattr("app.settings.is_production", lambda: False)
    assert validate_schema_version(engine) == "uyumsuz"   # açılış engellenmez, sessiz de kalmaz
