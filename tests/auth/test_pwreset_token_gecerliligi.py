"""
D04 (BUG #225) — ŞİFRE SIFIRLAMA BAĞLANTISI, ŞİFRE DEĞİŞTİKTEN SONRA HÂLÂ GEÇERLİYDİ.

Saldırı (denetimin çalıştırdığı PoC): posta kutusuna geçici erişim sağlayan biri
(paylaşılan bilgisayar, iletilmiş bir sıfırlama postası, ele geçirilmiş e-posta) bir
sıfırlama bağlantısını alıp BEKLETEBİLİYORDU. Kullanıcının doğru refleksi olan "hemen
şifremi değiştireyim" saldırganın elindeki bağlantıyı ÖLDÜRMÜYORDU: saldırgan 30 dakika
içinde şifreyi tekrar değiştirip hesabı kalıcı olarak ele geçiriyor, gerçek sahibini
dışarıda bırakıyordu. Hesabın içinde tüm banka bakiyeleri, borçlar, işlem geçmişi,
KVKK export'u (`GET /api/users/me/export`) ve `DELETE /api/users/me` var.

Kök neden: `create_password_reset_token` `token_version` claim'ini HİÇ geçirmiyordu
(payload `tv` daima 0) ve `password_reset_confirm` `token_version_ok(...)` çağırmıyordu.
BUG #172 ailesi access/refresh kolunu kapatmış, sıfırlama kolunu açık bırakmıştı.

İkinci senaryo aynı kökten: kullanıcı arka arkaya iki kez "şifremi unuttum" derse iki
bağlantı da 30 dk boyunca aynı anda canlı kalıyordu; birinin kullanılması diğerini
öldürmüyordu.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.auth as auth_mod
from app import auth as _auth
from app.dependencies import get_db
from app.main import app
from app.models import Base, User

ESKI_SIFRE = "Kurban-Sifre-123!"
KURBAN_YENI = "Kurban-Yeni-Sifre-456!"
SALDIRGAN_SIFRE = "Saldirgan-Sifre-789!"
EPOSTA = "kurban@ornek.com"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-prod-0123456789")
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"):
        monkeypatch.delenv(k, raising=False)   # SMTP yok → dev token dönsün
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(name="kurban", email=EPOSTA,
               password_hash=_auth.hash_password(ESKI_SIFRE), is_active=True))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    auth_mod._RATE.clear()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _sifirlama_token(client) -> str:
    r = client.post("/api/auth/password-reset-request", json={"email": EPOSTA})
    assert r.status_code == 200, r.text
    tok = r.json().get("_dev_token")
    assert tok, "dev token dönmedi (SMTP env'i temiz mi?)"
    return tok


def _giris(client, sifre: str):
    return client.post("/api/auth/login", json={"email": EPOSTA, "password": sifre})


def _erisim_basliklari(db) -> dict:
    u = db.query(User).filter(User.email == EPOSTA).first()
    return {"Authorization": f"Bearer {_auth.create_access_token(u.id, int(u.token_version or 0))}"}


# ============================================================
# 1. ANA SALDIRI — denetimin PoC'si
# ============================================================

def test_sifre_degisince_bekleyen_sifirlama_baglantisi_olur(client, db):
    """Kurbanın 'hemen şifremi değiştireyim' refleksi saldırganın bağlantısını ÖLDÜRMELİ."""
    calinan = _sifirlama_token(client)          # saldırgan bağlantıyı ele geçirdi, bekletiyor

    # Kurban doğru refleksi gösteriyor: şifresini kendi değiştiriyor
    r = client.post("/api/auth/change-password",
                    json={"current_password": ESKI_SIFRE, "new_password": KURBAN_YENI},
                    headers=_erisim_basliklari(db))
    assert r.status_code == 200, r.text

    # Saldırgan eski bağlantıyı kullanmaya çalışıyor
    r2 = client.post("/api/auth/password-reset-confirm",
                     json={"token": calinan, "new_password": SALDIRGAN_SIFRE})
    assert r2.status_code == 400, (
        f"Bekleyen sıfırlama bağlantısı şifre değişiminden SONRA hâlâ çalıştı "
        f"({r2.status_code}) — hesap ele geçirilebilir"
    )

    # Kurban içeride, saldırgan dışarıda
    assert _giris(client, KURBAN_YENI).status_code == 200, "Kurban kendi hesabından atıldı"
    assert _giris(client, SALDIRGAN_SIFRE).status_code == 401, "Saldırganın şifresi geçerli oldu"


def test_sifirlama_kullanildiktan_sonra_ikinci_baglanti_olur(client, db):
    """İki kez 'şifremi unuttum': birinin kullanılması diğerini de öldürmeli."""
    birinci = _sifirlama_token(client)
    ikinci = _sifirlama_token(client)
    assert birinci != ikinci

    r = client.post("/api/auth/password-reset-confirm",
                    json={"token": ikinci, "new_password": KURBAN_YENI})
    assert r.status_code == 200, r.text

    r2 = client.post("/api/auth/password-reset-confirm",
                     json={"token": birinci, "new_password": SALDIRGAN_SIFRE})
    assert r2.status_code == 400, (
        "Aynı anda canlı ikinci sıfırlama bağlantısı ilkinin kullanılmasından sonra da çalıştı"
    )
    assert _giris(client, KURBAN_YENI).status_code == 200


# ============================================================
# 2. MEŞRU AKIŞ BOZULMADI (L6: güvenlik kapısı ürünü kilitlemez)
# ============================================================

def test_normal_sifirlama_akisi_calisir(client, db):
    """Tek bağlantı, araya bir şey girmeden: sıfırlama çalışmalı."""
    tok = _sifirlama_token(client)
    r = client.post("/api/auth/password-reset-confirm",
                    json={"token": tok, "new_password": KURBAN_YENI})
    assert r.status_code == 200, r.text
    assert _giris(client, KURBAN_YENI).status_code == 200
    assert _giris(client, ESKI_SIFRE).status_code == 401


def test_ayni_token_iki_kez_kullanilamaz(client, db):
    """BUG #172 regresyonu: tek-kullanımlık kapısı hâlâ ayakta."""
    tok = _sifirlama_token(client)
    assert client.post("/api/auth/password-reset-confirm",
                       json={"token": tok, "new_password": KURBAN_YENI}).status_code == 200
    r2 = client.post("/api/auth/password-reset-confirm",
                     json={"token": tok, "new_password": SALDIRGAN_SIFRE})
    assert r2.status_code == 400


# ============================================================
# 3. TOKEN'IN KENDİSİ — tv claim'i gerçekten taşınıyor mu
# ============================================================

def test_sifirlama_tokeni_token_version_tasir(db):
    """`tv` claim'i 0 sabitiyse üstteki kapılar sessizce etkisiz kalır (denetim kanıtı)."""
    u = db.query(User).filter(User.email == EPOSTA).first()
    u.token_version = 7
    db.commit()

    tok = _auth.create_password_reset_token(u.id, int(u.token_version))
    payload = _auth.decode_token(tok, expected_type="pwreset")
    assert int(payload["tv"]) == 7, (
        f"pwreset token'ının tv claim'i {payload.get('tv')} — sürüm kontrolü etkisiz kalır"
    )
