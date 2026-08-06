"""
BUG #254 — ŞİFRE POLİTİKASI KİŞİYE ÖZEL TAHMİNİ GÖRMÜYORDU (+ blocklist inceydi).

BUG #187 politikayı "yalnız uzunluk"tan kurtarmıştı ama iki boşluk kaldı:

1. **Blocklist 30 kayıttı.** Sızıntı listelerinin tepesindeki pek çok şifre (`1q2w3e4r`,
   `letmein123`, `qwertyuiop`, `changeme`, TR varyantları) içinde YOKTU.
2. **Kişiye özel tahmin denetlenmiyordu.** Saldırgan e-postayı zaten bilir; hedefli
   denemede İLK sırada denenen şey `<e-posta-adı>+rakam` kalıbıdır (`ali@x.com` →
   `ali12345`). Bu şifre genel blocklist'te olmadığı için politikadan GEÇİYORDU.

Ölçüt bilinçli olarak "içeriyor mu" DEĞİL: `ali` parçası `Kaliteli!9x` içinde de geçer ve
güçlü bir şifreyi haksız yere reddederdik (L6 — kapı ürünü kıramaz). Gerçek zayıf desen,
kimliğin şifrenin GÖVDESİ olmasıdır: harf çekirdeği kimlikle BAŞLIYORSA reddedilir.
"""
from __future__ import annotations

import pytest

from app.auth import password_problems, _YAYGIN_SIFRELER


def test_blocklist_kapsam_tabani():
    """L23: liste sessizce küçülürse politika sessizce zayıflar."""
    assert len(_YAYGIN_SIFRELER) >= 100, f"Blocklist yalnız {len(_YAYGIN_SIFRELER)} kayıt"
    # İki dünyanın da temsil edildiğini ölç (global sızıntı + TR'ye özgü seçimler)
    assert {"1q2w3e4r", "letmein123", "changeme"} <= _YAYGIN_SIFRELER
    assert {"parola1234", "galatasaray", "merhaba123"} <= _YAYGIN_SIFRELER


@pytest.mark.parametrize("zayif", [
    "1q2w3e4r", "qwertyuiop", "letmein123", "changeme", "welcome123",
    "parola1234", "merhaba123", "besiktas1", "hesap123",
])
def test_yaygin_sifreler_reddedilir(zayif):
    assert password_problems(zayif), f"{zayif!r} politikadan geçti"


@pytest.mark.parametrize("sifre,eposta,ad", [
    ("ali12345", "ali@example.com", None),
    ("mehmet2026", None, "Mehmet"),
    ("ayse!2026", "ayse@example.com", None),
    ("MURAT1234", "murat@example.com", None),      # büyük harf de aynı desen
])
def test_kimlikle_baslayan_sifre_reddedilir(sifre, eposta, ad):
    sorunlar = password_problems(sifre, email=eposta, name=ad)
    assert any("e-posta" in s for s in sorunlar), f"{sifre!r} kişiye özel tahmini geçti"


@pytest.mark.parametrize("guclu,eposta", [
    ("Kaliteli!9x", "ali@example.com"),     # 'ali' İÇİNDE geçiyor ama gövde değil
    ("Xk9!mQ2vLp7z", "ali@example.com"),
    ("Hesabim-2026!Guvenli", "murat@example.com"),
])
def test_guclu_sifre_haksiz_reddedilmez(guclu, eposta):
    """L6: kapı ürünü kıramaz — 'içeriyor' ölçütü bu şifreleri yanlışlıkla reddederdi."""
    assert password_problems(guclu, email=eposta) == [], guclu


@pytest.mark.parametrize("dizi", ["abcdef99", "Q1234567", "xxqwertyui", "asdfghjkl0"])
def test_ardisik_dizi_reddedilir(dizi):
    assert password_problems(dizi), f"{dizi!r} ardışık dizi kontrolünden geçti"


def test_kayit_ucunda_kimlik_sifresi_reddedilir(monkeypatch):
    """Sözleşme uçta da geçerli: politika yalnız fonksiyonda kalırsa kapı yarımdır."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.main import app
    from app.dependencies import get_db
    from app.models import Base

    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "z" * 64)
    monkeypatch.setenv("REGISTRATION_MODE", "open")
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    app.dependency_overrides[get_db] = lambda: s
    try:
        c = TestClient(app)
        r = c.post("/api/auth/register", json={"email": "ali@example.com",
                                               "password": "ali12345", "kvkk_consent": True})
        assert r.status_code == 422, f"kişiye özel zayıf şifre uçtan geçti: {r.status_code}"
    finally:
        app.dependency_overrides.clear()
        s.close()
