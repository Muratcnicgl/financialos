"""
BUG #246 (denetim D32 + D33) — KİMLİKSİZ DIŞ-ÇAĞRI YÜZEYİ + DOĞRULANMAYAN TERCİH.

**D32:** `/api/prices/*` uçları kimlik de rate-limit de istemiyordu ve her istek TCMB
EVDS'ye **30 sn timeout'lu** senkron bir dış HTTP çağrısı tetikliyordu. Ölçüldü (denetim):
20 kimliksiz istek → 20 dış çağrı, 401/429 yok. Uçlar `def` (senkron) olduğu için
Starlette'in threadpool'u tükendiğinde **gerçek kullanıcılar cockpit/koç/işlem girişine
erişemez**; ayrıca operatörün EVDS kotası üçüncü şahıslarca yakılır (fiyatlar bayatlar).
Bugün EVDS_API_KEY tanımsız olduğu için sömürü kapalı — yani bu, tek bir env değişkeni
uzaklıktaki **latent** bir açık: "şu an zararsız" bir kapıyı açık bırakmak, onu kapatmak
için gereken tek satırdan daha pahalıdır.

**D33:** `PUT /api/user` para birimini hiç doğrulamadan saklıyordu (`'XYZ'`, `'!!!'`,
`'   '` → 200) ama tüm arayüz sabit `TL` gösteriyor. Kullanıcı "ayarladım" sanıp tutarları
YANLIŞ para biriminde okur. Aynı uçtaki `timezone` dalı geçersiz değeri 422 ile reddediyor
— yani sözleşme kendi içinde tutarsızdı. `locale` de aynı durumdaydı.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="test", email="t@x.com"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def kimliksiz_client(db_session, monkeypatch):
    """Kimlik doğrulama AÇIK, oturum YOK — gerçek beta kurulumunun karşılaştığı istemci."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ============================================================
# D32 — fiyat uçları kimliksiz dış çağrı tetikleyemez
# ============================================================

def test_fiyat_ucu_kimliksiz_dis_cagri_tetiklemez(kimliksiz_client):
    with patch("app.routers.prices.fetch_currency_rate") as sahte:
        r = kimliksiz_client.get("/api/prices/currency/USD")
    assert r.status_code == 401, f"kimliksiz istek {r.status_code} döndü (401 bekleniyordu)"
    assert sahte.call_count == 0, "Kimlik doğrulanmadan dış servise çağrı yapıldı"


def test_altin_ucu_de_kimlik_ister(kimliksiz_client):
    with patch("app.routers.prices.fetch_gold_price") as sahte:
        r = kimliksiz_client.get("/api/prices/gold/bilesik")
    assert r.status_code == 401
    assert sahte.call_count == 0


def test_giris_yapmis_kullanici_fiyat_alabilir(client):
    """L6: kapı ürünü kıramaz — panel bu ucu kullanmaya devam eder."""
    with patch("app.routers.prices.fetch_currency_rate",
               return_value={"buy": 46.9, "sell": 47.0, "date": "2026-08-06", "source": "evds"}):
        r = client.get("/api/prices/currency/USD")
    assert r.status_code == 200 and r.json()["rate_sell"] == "47.0"


def test_fiyat_uclari_rate_limit_bagimliligi_tasir():
    """Kimlik + kota: tek kullanıcı da dış kotayı yakabilir (statik sözleşme)."""
    from pathlib import Path
    kaynak = (Path(__file__).resolve().parent.parent / "app" / "routers" / "prices.py"
              ).read_text(encoding="utf-8")
    assert "get_current_user" in kaynak, "Fiyat uçları kimlik istemiyor"
    assert "rate_limit" in kaynak, "Fiyat uçlarında hız sınırı yok (dış kota tüketilebilir)"


# ============================================================
# D33 — tercihler doğrulanmadan saklanamaz
# ============================================================

@pytest.mark.parametrize("gecersiz", ["XYZ", "!!!", "   ", "zzz"])
def test_gecersiz_para_birimi_reddedilir(client, gecersiz):
    r = client.put("/api/user", json={"currency": gecersiz})
    assert r.status_code == 422, f"{gecersiz!r} kabul edildi ({r.status_code})"


@pytest.mark.parametrize("gecerli", ["TRY", "try", " TRY "])
def test_desteklenen_para_birimi_kabul_edilir(client, gecerli):
    r = client.put("/api/user", json={"currency": gecerli.strip()})
    assert r.status_code == 200
    assert r.json()["currency"] == "TRY"


@pytest.mark.parametrize("gosterilmeyen", ["USD", "EUR", "GBP"])
def test_gosterilemeyen_para_birimi_kabul_EDILMEZ(client, gosterilmeyen):
    """BUG #251: geçerli ISO kodu olması yetmez — arayüz her yerde TL yazıyor ve hiçbir
    katman kur çevirmiyor. Kabul etmek, kullanıcıya "ayarladım" sandıran ama karşılığı
    olmayan bir düğme vermektir (D33'ün ASIL şikâyeti). Küme ADR-042 ile büyüyecek."""
    r = client.put("/api/user", json={"currency": gosterilmeyen})
    assert r.status_code == 422
    assert "ADR-042" in r.text or "kur" in r.text.lower()


def test_gecersiz_locale_reddedilir(client):
    r = client.put("/api/user", json={"locale": "xx-BOGUS"})
    assert r.status_code == 422


def test_gecerli_locale_kabul(client):
    assert client.put("/api/user", json={"locale": "tr-TR"}).status_code == 200


def test_saat_dilimi_dogrulamasi_korunuyor(client):
    """Regresyon: aynı uçtaki tutarlı dal bozulmasın."""
    assert client.put("/api/user", json={"timezone": "Mars/Olympus"}).status_code == 422
    assert client.put("/api/user", json={"timezone": "Europe/Istanbul"}).status_code == 200
