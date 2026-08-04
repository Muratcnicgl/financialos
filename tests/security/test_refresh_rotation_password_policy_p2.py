"""
P2 (Wave-9) — BUG #186 (refresh rotasyonu) + #187 (şifre politikası).

BUG #186: `/api/auth/refresh` eski refresh token'ı iptal etmiyor ve YENİ refresh
  üretmiyordu. Çalınmış bir refresh token 30 gün boyunca sınırsız kez kullanılabiliyordu;
  kurban da aynı token'ı kullandığı için "aynı token iki taraftan kullanıldı" sinyali
  (reuse detection) hiç oluşmuyordu → sızıntı asla fark edilmezdi.
  Çözüm (OAuth 2.1 / RFC 9700 önerisi): her kullanımda ROTASYON — eski jti kara listeye,
  yeni refresh döner. Kara listedeki bir refresh yeniden kullanılırsa bu bir SIZINTI
  sinyalidir → kullanıcının tüm oturumları düşürülür (token_version artırılır).

BUG #187: şifre politikası yalnız uzunluktu (>=8). "12345678", "parola123" gibi ilk-1000
  listesindeki şifreler kabul ediliyordu.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base, User


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-refresh-rotation-0123456789abcdef")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    # SMTP tanımsız → dev-token dalı (sıfırlama akışını token'sız sınayamayız)
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_PASS", "SMTP_FROM"):
        monkeypatch.delenv(k, raising=False)
    from app import rate_limit
    rate_limit.reset()


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def kayitli(client):
    r = client.post("/api/auth/register", json={
        "email": "rot@example.com", "password": "Guclu-Parola-2026!",
        "name": "Rot", "kvkk_consent": True})
    assert r.status_code == 201, r.text[:200]
    return r.json()


# ── BUG #186: refresh rotasyonu + tekrar-kullanım tespiti ───────────────────

def test_refresh_yeni_token_dondurur(client, kayitli):
    r = client.post("/api/auth/refresh", json={"refresh_token": kayitli["refresh_token"]})
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert body.get("refresh_token"), "Rotasyon yok — yanıtta yeni refresh token dönmüyor"
    assert body["refresh_token"] != kayitli["refresh_token"]


def test_eski_refresh_rotasyondan_sonra_calismaz(client, kayitli):
    eski = kayitli["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": eski})
    assert r.status_code == 200
    r2 = client.post("/api/auth/refresh", json={"refresh_token": eski})
    assert r2.status_code == 401, (
        f"Eski refresh token rotasyondan sonra hâlâ çalışıyor ({r2.status_code})"
    )


def test_tekrar_kullanim_tum_oturumlari_dusurur(client, kayitli, db):
    """Sızıntı sinyali: kara listedeki refresh yeniden kullanılırsa TÜM oturumlar ölür."""
    eski = kayitli["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": eski})
    yeni = r.json()["refresh_token"]

    # Saldırgan eski (çalınmış) token'ı deniyor → tespit
    assert client.post("/api/auth/refresh", json={"refresh_token": eski}).status_code == 401

    # Kurbanın elindeki güncel token da düşmeli (hesap kilitlenir, yeniden giriş gerekir)
    r3 = client.post("/api/auth/refresh", json={"refresh_token": yeni})
    assert r3.status_code == 401, (
        "Tekrar-kullanım tespit edildi ama oturumlar düşürülmedi — saldırgan erişimde kalır"
    )


def test_rotasyon_sonrasi_access_calisir(client, kayitli):
    """Pozitif kontrol: normal akış bozulmadı."""
    r = client.post("/api/auth/refresh", json={"refresh_token": kayitli["refresh_token"]})
    access = r.json()["access_token"]
    assert client.get("/api/auth/me",
                      headers={"Authorization": f"Bearer {access}"}).status_code == 200


# ── BUG #187: şifre politikası ──────────────────────────────────────────────

@pytest.mark.parametrize("zayif", ["12345678", "password", "parola123", "qwerty123",
                                   "11111111", "iloveyou"])
def test_yaygin_sifreler_reddedilir(client, zayif):
    r = client.post("/api/auth/register", json={
        "email": f"z{abs(hash(zayif)) % 10000}@example.com", "password": zayif,
        "name": "Zayif", "kvkk_consent": True})
    assert r.status_code == 422, f"Yaygın şifre '{zayif}' kabul edildi ({r.status_code})"


def test_guclu_sifre_kabul_edilir(client):
    r = client.post("/api/auth/register", json={
        "email": "guclu@example.com", "password": "Kirmizi-Fener-2026!",
        "name": "Guclu", "kvkk_consent": True})
    assert r.status_code == 201, r.text[:200]


def test_sifirlamada_da_politika_uygulanir(client, kayitli):
    """Politika yalnız kayıtta değil, şifre sıfırlamada da geçerli olmalı."""
    r = client.post("/api/auth/password-reset-request", json={"email": "rot@example.com"})
    token = r.json().get("_dev_token")
    assert token
    r = client.post("/api/auth/password-reset-confirm",
                    json={"token": token, "new_password": "password"})
    assert r.status_code == 422, f"Sıfırlamada zayıf şifre kabul edildi ({r.status_code})"


# ══════════════════════════════════════════════════════════════════════════════
# BUG #190 (P3) — giriş yapmış kullanıcı şifresini DEĞİŞTİREMİYORDU
# Tek yol e-posta ile sıfırlamaydı; prod'da SMTP yapılandırılmamışsa (yeni deploy,
# ücretsiz kademe beklerken) kullanıcı şifresini hiç değiştiremiyordu.
# ══════════════════════════════════════════════════════════════════════════════

def test_sifre_degistirme_ucu_calisir(client, kayitli):
    h = {"Authorization": f"Bearer {kayitli['access_token']}"}
    r = client.post("/api/auth/change-password", headers=h, json={
        "current_password": "Guclu-Parola-2026!", "new_password": "Yepyeni-Parola-2026!"})
    assert r.status_code == 200, r.text[:200]

    # Yeni şifreyle giriş çalışır, eskisi çalışmaz
    assert client.post("/api/auth/login", json={
        "email": "rot@example.com", "password": "Yepyeni-Parola-2026!"}).status_code == 200
    assert client.post("/api/auth/login", json={
        "email": "rot@example.com", "password": "Guclu-Parola-2026!"}).status_code == 401


def test_yanlis_mevcut_sifre_reddedilir(client, kayitli):
    h = {"Authorization": f"Bearer {kayitli['access_token']}"}
    r = client.post("/api/auth/change-password", headers=h, json={
        "current_password": "Yanlis-Parola-2026!", "new_password": "Yepyeni-Parola-2026!"})
    assert r.status_code == 401, f"Mevcut şifre doğrulanmadan değiştirildi ({r.status_code})"


def test_degistirmede_de_politika_uygulanir(client, kayitli):
    h = {"Authorization": f"Bearer {kayitli['access_token']}"}
    r = client.post("/api/auth/change-password", headers=h, json={
        "current_password": "Guclu-Parola-2026!", "new_password": "12345678"})
    assert r.status_code == 422


def test_degistirme_diger_oturumlari_dusurur(client, kayitli):
    """Güvenlik: şifre değişince ÇALINMIŞ diğer oturumlar ölmeli (BUG #172 ailesi)."""
    eski_refresh = kayitli["refresh_token"]
    h = {"Authorization": f"Bearer {kayitli['access_token']}"}
    r = client.post("/api/auth/change-password", headers=h, json={
        "current_password": "Guclu-Parola-2026!", "new_password": "Yepyeni-Parola-2026!"})
    assert r.status_code == 200
    assert client.post("/api/auth/refresh",
                       json={"refresh_token": eski_refresh}).status_code == 401


def test_degistirme_cagirana_yeni_token_verir(client, kayitli):
    """Kullanıcı deneyimi: şifresini değiştiren kişi anında atılmamalı."""
    h = {"Authorization": f"Bearer {kayitli['access_token']}"}
    r = client.post("/api/auth/change-password", headers=h, json={
        "current_password": "Guclu-Parola-2026!", "new_password": "Yepyeni-Parola-2026!"})
    yeni = r.json()
    assert yeni.get("access_token") and yeni.get("refresh_token")
    assert client.get("/api/auth/me",
                      headers={"Authorization": f"Bearer {yeni['access_token']}"}).status_code == 200
