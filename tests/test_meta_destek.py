"""
P8 / BUG #210 — DESTEK KANALI: giriş yapamayan kullanıcının ulaşabileceği yol yoktu.

Destek adresi yalnızca e-posta şablonlarının içinde yaşıyordu; yani kullanıcı ancak
şifre sıfırlama e-postası ALABİLİRSE destekten haberdar oluyordu. Giriş yapamayan
(yanlış şifre / doğrulanmamış e-posta / davet kodu çalışmıyor) bir beta kullanıcısının
ürünle iletişim kurmasının hiçbir yolu yoktu — kullanıcı rehberi bile "davet kodunu
ileten kişiye yaz" diyordu. Açık betada (P8) doğrudan kullanıcı kaybı + KVKK'nın
"veri sorumlusuna başvuru" hakkının fiilen kullanılamaması demek.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.legal import BELGELER


@pytest.fixture
def client():
    return TestClient(app)


def test_kunye_kimliksiz_erisilebilir(client):
    """Giriş YAPAMAYAN kullanıcı da görebilmeli — token istenmemeli."""
    r = client.get("/api/meta")
    assert r.status_code == 200, "Künye kimlik istiyor: giriş yapamayan kullanıcı göremez"


def test_destek_adresi_bos_donmez(client):
    d = client.get("/api/meta").json()["destek"]
    assert d and d.strip(), "Destek kanalı boş — kullanıcı kime yazacağını bilemez"


def test_destek_adresi_env_ile_yonetilir(client, monkeypatch):
    """BUG #205 dersi: kişisel adres koda GÖMÜLMEZ, operatör env'den belirler."""
    monkeypatch.setenv("SUPPORT_EMAIL", "destek@ornek-urun.com")
    assert client.get("/api/meta").json()["destek"] == "destek@ornek-urun.com"


def test_kisisel_eposta_sizmaz(client):
    """Künye jenerik olmalı; kişisel gmail/hotmail adresi yayınlanmamalı."""
    import re
    govde = client.get("/api/meta").text
    assert not re.search(r"[\w\.\-]+@(gmail|hotmail|outlook|yahoo|yandex)\.", govde), \
        "Künyede kişisel e-posta adresi var"


def test_kayit_modu_giris_ekranina_bildirilir(client, monkeypatch):
    """Giriş ekranı davet kodunun ZORUNLU olduğunu söyleyebilmeli (yoksa kullanıcı
    kodu boş bırakır, kayıt reddedilir, sebebini anlamaz)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    j = client.get("/api/meta").json()
    assert j["kayit_modu"] == "invite_only" and j["davet_kodu_gerekli"] is True

    monkeypatch.setenv("REGISTRATION_MODE", "open")
    j = client.get("/api/meta").json()
    assert j["kayit_modu"] == "open" and j["davet_kodu_gerekli"] is False


def test_hukuki_baglantilar_gercekten_calisir(client):
    """Elle yazılan slug kopyası zamanla kayar ve giriş ekranı 404'e link verir."""
    hukuki = client.get("/api/meta").json()["hukuki"]
    assert hukuki, "Kayıt öncesi okunacak hukuki metin bağlantısı yok"
    assert set(hukuki) == set(BELGELER), "Künyedeki slug listesi legal router ile kaymış"
    for url in hukuki.values():
        assert client.get(url).status_code == 200, f"Kırık hukuki bağlantı: {url}"


def test_surum_bildirilir(client):
    """Kullanıcı hata bildirdiğinde 'hangi kod koşuyordu' ölçülebilmeli (BUG #200)."""
    j = client.get("/api/meta").json()
    from app.version import APP_VERSION
    assert j["surum"] == APP_VERSION


def test_durum_ucu_kimliksiz_ve_sade(client):
    """'Bende mi, sizde mi?' — ayrıntı vermeden servis durumu."""
    r = client.get("/api/meta/durum")
    assert r.status_code == 200
    j = r.json()
    assert j["saglikli"] is True and j["veritabani"] is True


def test_durum_ucu_operasyon_ayrintisi_sizdirmaz(client):
    """İş adları/hata tipleri /api/ops altında kalmalı (kimlik ister)."""
    govde = client.get("/api/meta/durum").text.lower()
    for sizinti in ("traceback", "sqlite", "postgres", "password", "job", "cron"):
        assert sizinti not in govde, f"Durum ucu operasyon ayrıntısı sızdırıyor: {sizinti}"


# ── Production fail-fast: destek kanalı tanımsız bırakılamaz ──────────────────

def test_production_destek_adresi_zorunlu(monkeypatch):
    """Tanımsız SUPPORT_EMAIL sessizce geçerse kullanıcı kaybedilir → startup'ta patla."""
    from app.settings import validate_security_config
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.delenv("SUPPORT_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="SUPPORT_EMAIL"):
        validate_security_config()


def test_production_gecerli_adresle_baslar(monkeypatch):
    from app.settings import validate_security_config
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SUPPORT_EMAIL", "destek@ornek-urun.com")
    validate_security_config()


def test_smtp_gonderen_adresi_destek_yerine_gecmez(monkeypatch):
    """Eski hal sessizce SMTP_FROM'a düşüyordu: operatörün ŞAHSİ posta kutusu
    kimliksiz /api/meta ucundan yayınlanırdı."""
    from app.services.email import destek_adresi
    monkeypatch.delenv("SUPPORT_EMAIL", raising=False)
    monkeypatch.setenv("SMTP_FROM", "sahsi.adres@gmail.com")
    assert "gmail" not in destek_adresi()
