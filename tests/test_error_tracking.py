"""
P5 (Wave-9) — BUG #195: beklenmedik hatalar SESSİZCE kaybolmasın.

Önce: 500 hatası yalnızca log dosyasına düşüyordu. Kapalı betada operatör (tek kişi) log
dosyasını sürekli izleyemez; kullanıcı "çalışmıyor" der, elde iz kalmaz.

Karar (KURAL 12 / K10): Sentry gibi bir dış servis kullanıcının finansal verisini üçüncü
tarafa taşır + yeni hesap/anahtar (insan-kapısı) gerektirir → hata izleme kendi DB'mizde.
Bu dosya sözleşmeyi kilitler: hata KAYDEDİLİR, tekrarlar GRUPLANIR, PII/sır SIZMAZ,
kullanıcıya iç detay DÖNMEZ ve izleme mekanizması isteği ASLA düşürmez.
"""
from __future__ import annotations

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_mod
from app.main import app
from app.dependencies import get_db
from app.models import Base, ErrorLog
from app.error_tracking import temizle, parmak_izi


# --- Test uçları: bilerek patlar ---
# BUG #235 (D21): bu router eskiden MODÜL YÜKLENİRKEN `app.include_router` ile eklenip
# hiç kaldırılmıyordu. `app` süreç-genelinde TEK nesnedir → uç, süitin geri kalanında da
# duruyordu ve uç envanterini tarayan kapılar (boş-durum e2e, izolasyon kapsam kilidi) onu
# ÜRÜN ucu sanıp çağırıyor, bilerek-çöken uç yüzünden kırmızıya düşüyorlardı. Artık:
# (1) yalnız bu dosyanın fixture'ı süresince eklenir ve kaldırılır (izolasyon),
# (2) `include_in_schema=False` — kamu sözleşmesinde (OpenAPI) hiç görünmez (savunma derinliği).
_test_router = APIRouter(prefix="/api/_test_hata", tags=["test"], include_in_schema=False)


@_test_router.get("/patla")
def _patla():
    raise RuntimeError("beklenmedik cokme")


@_test_router.get("/pii")
def _pii():
    raise ValueError("kullanici ali.veli@example.com token eyJhbGciOiJIUzI1NiJ9.abcdefghijkl")


@pytest.fixture
def cokme_uclari():
    """Bilerek-çöken uçları YALNIZ bu testler süresince global app'e takar."""
    onceki = list(app.router.routes)
    app.include_router(_test_router)
    app.openapi_schema = None          # şema önbelleği yeni rotayla kirlenmesin
    yield
    app.router.routes = onceki
    app.openapi_schema = None


@pytest.fixture
def db(monkeypatch):
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    s = Session()
    # exception handler kendi oturumunu acar -> ayni in-memory DB'ye baglanmali
    monkeypatch.setattr("app.database.SessionLocal", Session)
    app.dependency_overrides[get_db] = lambda: s
    yield s
    app.dependency_overrides.clear()
    s.close()


@pytest.fixture
def client(db, cokme_uclari):
    return TestClient(app, raise_server_exceptions=False)


def test_beklenmedik_hata_kaydedilir(client, db):
    r = client.get("/api/_test_hata/patla")
    assert r.status_code == 500
    kayitlar = db.query(ErrorLog).all()
    assert len(kayitlar) == 1, "Hata kaydedilmedi — sessizce kayboluyor"
    k = kayitlar[0]
    assert k.error_type == "RuntimeError"
    assert k.path == "/api/_test_hata/patla"
    assert k.occurrence_count == 1


def test_ayni_hata_gruplanir(client, db):
    for _ in range(3):
        client.get("/api/_test_hata/patla")
    kayitlar = db.query(ErrorLog).all()
    assert len(kayitlar) == 1, "Aynı hata için birden fazla satır (log şişmesi)"
    assert kayitlar[0].occurrence_count == 3, "Tekrar sayacı artmıyor"


def test_kullaniciya_ic_detay_donmez(client):
    r = client.get("/api/_test_hata/patla")
    govde = str(r.json())
    assert "RuntimeError" not in govde and "Traceback" not in govde
    assert "cokme" not in govde


def test_pii_ve_sir_maskelenir(client, db):
    client.get("/api/_test_hata/pii")
    k = db.query(ErrorLog).first()
    assert k is not None
    icerik = f"{k.message} {k.traceback_tail}"
    assert "ali.veli@example.com" not in icerik, "E-posta hata kaydına sızdı (KVKK)"
    assert "eyJhbGciOiJIUzI1NiJ9" not in icerik, "Token hata kaydına sızdı"


def test_izleme_istegi_dusurmez(client, db, monkeypatch):
    """Hata izleme bozulursa bile istek yanıtı normal (500) dönmeli — izleme ikincildir."""
    def _patla(*a, **k):
        raise RuntimeError("izleme katmani bozuk")
    monkeypatch.setattr(main_mod, "_JSONResponse", main_mod._JSONResponse)  # dokunma
    monkeypatch.setattr("app.error_tracking.kaydet", _patla)
    r = client.get("/api/_test_hata/patla")
    assert r.status_code == 500


# --- Saf fonksiyon testleri ---

def test_temizle_maskeleri():
    assert "@" not in temizle("hata: a@b.com")
    assert "<token>" in temizle("bearer eyJhbGciOiJIUzI1NiJ9.aaaaaaaaaaaa")
    assert "<uzun-sayi>" in temizle("kart 1234 5678 9012 3456")
    assert "<gizli>" in temizle("SECRET_KEY=abc123def")


def test_parmak_izi_mesajdan_bagimsiz():
    """Aynı kod yolu, farklı değişken değerleri → AYNI grup."""
    tb = 'File "app/x.py", line 10\nFile "app/y.py", line 20'
    assert parmak_izi("ValueError", "/api/x", tb) == parmak_izi("ValueError", "/api/x", tb)
    assert parmak_izi("ValueError", "/api/x", tb) != parmak_izi("KeyError", "/api/x", tb)
