"""
D05 (BUG #226) — OAUTH CALLBACK KAPALI-BETA DAVET KAPISINI TAMAMEN ATLIYORDU.

BUG #199'un tüm gerekçesi "kapalı beta bir iddia değil KONTROL olsun" idi; `invite_required()`
yalnızca `POST /api/auth/register` içinde çağrılıyordu. OAuth yapılandırılmış bir canlıda
alan adını bilen herkes Google/GitHub ile tek tıkla hesap açabiliyordu — aynı e-posta
`/register`'da 403 alırken. Denetimin PoC'si oturumun sonuna kadar gitti: kullanıcı
yaratılıyor, `POST /api/auth/oauth/exchange` 200 dönüyor, `GET /api/auth/me` 200.

Etki: (a) davetsiz, izlenemeyen kullanıcılar KVKK'da veri-sorumlusu yükümlülüğü doğurur ve
envanterde görünmez; (b) her yeni kullanıcı paylaşılan LLM sağlayıcı kotasını tüketir —
gerçek davetliler koçu kullanamaz hale gelir; (c) operatörün "kimler betada" listesi
(`BetaInvite`) gerçekle uyuşmaz; (d) `/api/meta` kimliksiz olarak `davet_kodu_gerekli: true`
beyan ediyordu — ürün uygulamadığı bir kontrolü ilan ediyordu.

Kapı tasarımı: OAuth akışında davet kodu girilecek bir alan YOK (kullanıcı sağlayıcıya
gidip geliyor). Bu yüzden kapı **e-posta eşleşmeli davet** üzerinden kurulur: davetli-only
modda YENİ bir OAuth kullanıcısı ancak kendi e-postasına açılmış, kullanılmamış ve süresi
geçmemiş bir davet varsa yaratılır; davet aynı transaction'da TÜKETİLİR. MEVCUT kullanıcının
girişi etkilenmez (davet kayıt kapısıdır, giriş kapısı değil).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base, BetaInvite, User
import app.routers.auth as auth_mod
import app.services.oauth as oauth_mod
from app.beta_access import davet_olustur

EPOSTA = "yabanci@ornek.com"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-prod-0123456789")
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "gid.apps.googleusercontent.com")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "GOCSPX-secret")
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")   # kapalı beta


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    auth_mod._RATE.clear()
    oauth_mod._states.clear()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _callback(client, monkeypatch, email: str = EPOSTA, sub: str = "G1"):
    monkeypatch.setattr(
        auth_mod._oauth, "exchange_code",
        lambda p, c, code_verifier=None: {"provider": "google", "sub": sub,
                                          "email": email, "name": "Yabanci"},
    )
    st = oauth_mod.new_state()
    return client.get(f"/api/auth/callback/google?code=abc&state={st}", follow_redirects=False)


# ============================================================
# 1. KAPI — davetsiz OAuth kaydı
# ============================================================

def test_davetsiz_oauth_yeni_hesap_acamaz(client, db, monkeypatch):
    """Denetimin PoC'si: davetsiz Google girişi hesap AÇMAMALI."""
    r = _callback(client, monkeypatch)
    assert r.status_code == 403, (
        f"Davetli-only modda davetsiz OAuth {r.status_code} döndü — kapalı beta fail-open"
    )
    assert db.query(User).filter(User.email == EPOSTA).first() is None, \
        "Davetsiz OAuth kullanıcısı yine de yaratıldı"


def test_register_ile_ayni_davranis(client, db, monkeypatch):
    """Aynı e-posta iki kayıt yolunda AYNI cevabı almalı (kapı yola göre değişmez)."""
    r_register = client.post("/api/auth/register",
                             json={"email": EPOSTA, "password": "Guclu-Sifre-123!",
                                   "kvkk_consent": True})
    r_oauth = _callback(client, monkeypatch)
    assert r_register.status_code == 403
    assert r_oauth.status_code == 403, (
        f"/register 403 derken OAuth {r_oauth.status_code} — kapı yola göre değişiyor"
    )


# ============================================================
# 2. MEŞRU AKIŞ — davetli kullanıcı girebilmeli (L6)
# ============================================================

def test_e_postasina_davet_acilmis_kullanici_girebilir(client, db, monkeypatch):
    """Operatör davetliyi e-postasıyla davet ettiyse OAuth girişi çalışmalı."""
    davet = davet_olustur(db, email=EPOSTA, note="beta davetlisi")
    r = _callback(client, monkeypatch)
    assert r.status_code == 307, r.text
    u = db.query(User).filter(User.email == EPOSTA).first()
    assert u is not None and u.oauth_provider == "google"

    db.refresh(davet)
    assert davet.used_at is not None, "Davet tüketilmedi — tek kullanımlık kapısı delik"
    assert davet.used_by_user_id == u.id, "Davet hangi kullanıcıya gitti izlenemiyor"


def test_davet_buyuk_kucuk_harf_duyarsiz(client, db, monkeypatch):
    """Operatör adresi büyük harfle girdiyse davetli dışarıda kalmamalı."""
    davet_olustur(db, email="Yabanci@Ornek.COM")
    r = _callback(client, monkeypatch, email=EPOSTA)
    assert r.status_code == 307, r.text


def test_mevcut_kullanicinin_girisi_davet_gerektirmez(client, db, monkeypatch):
    """Davet KAYIT kapısıdır, giriş kapısı değil — mevcut kullanıcı davetsiz girebilir."""
    db.add(User(email=EPOSTA, name="Var", password_hash="x", is_active=True))
    db.commit()
    r = _callback(client, monkeypatch)
    assert r.status_code == 307, (
        f"Mevcut kullanıcı OAuth girişinde {r.status_code} aldı — kapı girişi de kilitliyor"
    )


def test_acik_kayit_modunda_kapi_kapali_degil(client, db, monkeypatch):
    """REGISTRATION_MODE=open iken davranış eskisi gibi (kapı yalnız davetli-only'de)."""
    monkeypatch.setenv("REGISTRATION_MODE", "open")
    r = _callback(client, monkeypatch)
    assert r.status_code == 307, r.text
    assert db.query(User).filter(User.email == EPOSTA).first() is not None


# ============================================================
# 3. DAVETİN KENDİ SINIRLARI OAUTH YOLUNDA DA GEÇERLİ
# ============================================================

def test_kullanilmis_davet_ikinci_kez_hesap_acmaz(client, db, monkeypatch):
    """Tek-kullanımlık: aynı davetle ikinci bir OAuth hesabı açılamaz."""
    davet_olustur(db, email=EPOSTA)
    assert _callback(client, monkeypatch).status_code == 307
    db.query(User).filter(User.email == EPOSTA).delete()   # kullanıcı silindi, davet tükendi
    db.commit()
    r = _callback(client, monkeypatch)
    assert r.status_code == 403, "Tükenmiş davetle yeniden hesap açıldı"


def test_suresi_gecmis_davet_kabul_edilmez(client, db, monkeypatch):
    from datetime import datetime, timedelta, timezone as _tz
    davet = davet_olustur(db, email=EPOSTA)
    davet.expires_at = datetime.now(_tz.utc).replace(tzinfo=None) - timedelta(days=1)
    db.commit()
    assert _callback(client, monkeypatch).status_code == 403


def test_baska_e_postaya_acilmis_davet_ise_yaramaz(client, db, monkeypatch):
    davet_olustur(db, email="baskasi@ornek.com")
    assert _callback(client, monkeypatch).status_code == 403


def test_e_postasiz_genel_davet_kodu_oauth_yolunu_acmaz(client, db, monkeypatch):
    """E-postasız (yalnız-kod) davet OAuth'ta eşleştirilemez → fail-closed kalmalı.

    Aksi halde tek bir genel kod, adres bilmeden sınırsız OAuth hesabı açardı.
    """
    davet_olustur(db, email=None, note="genel kod")
    assert _callback(client, monkeypatch).status_code == 403


# ============================================================
# 4. İLAN EDİLEN KONTROL GERÇEKTEN UYGULANIYOR MU (L8)
# ============================================================

def test_meta_beyani_kodda_karsiligi_var(client, db, monkeypatch):
    """/api/meta `davet_kodu_gerekli: true` diyorsa HER kayıt yolu bunu uygulamalı."""
    r = client.get("/api/meta")
    assert r.status_code == 200, r.text
    if r.json().get("davet_kodu_gerekli") is not True:
        pytest.skip("meta bu kurulumda davet gerekli demiyor")
    assert _callback(client, monkeypatch).status_code == 403, \
        "meta 'davet gerekli' beyan ediyor ama OAuth yolu davetsiz hesap açıyor"
