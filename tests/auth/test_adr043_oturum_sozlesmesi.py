"""
ADR-043 (P2.1) — OTURUM SÖZLEŞMESİ BELGEYE DEĞİL KOŞUMA BAĞLI.

"Oturum sabitlemesi" başlığı güvenlik review'unda yazılı gerekçesi olmadan duruyordu: karar
koda uygulanmıştı (JWT + `token_version` + refresh rotasyonu) ama HİÇBİR YERDE yazılı
değildi — yani gelecekteki bir değişiklik onu bilmeden bozabilirdi. ADR-043 kararı yazar;
bu dosya da ADR'nin kanıt tablosunu ölçer.

L17 dersi: bir belgenin "uygulandı" iddiası kanıt değildir. ADR'de adı geçen her test
GERÇEKTEN var olmalı ve davranış sözleşmesi ayrıca ölçülmeli — aksi halde testler yeniden
adlandırılınca ADR sessizce yalana döner.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent.parent
ADR = KOK / "docs" / "architecture" / "adr-043-oturum-sabitleme-ve-token-yasam-dongusu.md"


def _adr_metni() -> str:
    assert ADR.exists(), f"ADR-043 yok: {ADR}"
    return ADR.read_text(encoding="utf-8")


def _atif_yapilan_testler() -> list[tuple[str, str]]:
    """ADR'nin kanıt tablosundaki `dosya::test_adi` atıfları."""
    return re.findall(r"`(tests/[\w/]+\.py)::(test_\w+)`", _adr_metni())


def test_adr_kanit_tablosu_bos_degil():
    """L23: atıf bulunamazsa alttaki kapı sessizce boş koşar."""
    atiflar = _atif_yapilan_testler()
    assert len(atiflar) >= 5, f"ADR-043 yalnız {len(atiflar)} teste atıf yapıyor"


def test_adr_de_adi_gecen_her_test_gercekten_var():
    eksikler = []
    for dosya, ad in _atif_yapilan_testler():
        yol = KOK / dosya
        if not yol.exists():
            eksikler.append(f"{dosya} (dosya yok)")
            continue
        if f"def {ad}(" not in yol.read_text(encoding="utf-8"):
            eksikler.append(f"{dosya}::{ad}")
    assert not eksikler, (
        f"ADR-043 var olmayan testlere atıf yapıyor: {eksikler}. Belge, kendisini ölçen "
        "koşumdan koptu — iddia hâline geldi (L17)."
    )


def test_adr_kabul_edilen_riski_acikca_yaziyor():
    """Kabul edilen risk (localStorage) SESSİZ kalamaz — okuyan bilmeli."""
    metin = _adr_metni().lower()
    assert "localstorage" in metin and "kabul edilmiş risk" in metin


# ============================================================
# DAVRANIŞ — ADR'nin çekirdek iddiası: yetki değişince ESKİ token ölür
# ============================================================

@pytest.fixture
def ortam(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.main import app
    from app.dependencies import get_db
    from app.models import Base

    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "q" * 64)
    monkeypatch.setenv("REGISTRATION_MODE", "open")
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    app.dependency_overrides[get_db] = lambda: s
    c = TestClient(app)
    try:
        yield c, s
    finally:
        app.dependency_overrides.clear()
        s.close()


def _kayit(c) -> str:
    r = c.post("/api/auth/register", json={"email": "oturum@example.com",
                                           "password": "Gucluu-Parolam-2026!",
                                           "kvkk_consent": True})
    assert r.status_code == 201, r.text[:200]
    return r.json()["access_token"]


def test_sifre_degisince_eski_access_token_olur(ortam):
    """ADR-043 madde 2: fixation'ın gerçek zararı 'eski kimlik yetkili kalır'dır."""
    c, _ = ortam
    token = _kayit(c)
    basliklar = {"Authorization": f"Bearer {token}"}
    assert c.get("/api/auth/me", headers=basliklar).status_code == 200

    r = c.post("/api/auth/change-password", headers=basliklar,
               json={"current_password": "Gucluu-Parolam-2026!",
                     "new_password": "Baska-Guclu-Parola-77!"})
    assert r.status_code == 200, r.text[:200]

    assert c.get("/api/auth/me", headers=basliklar).status_code == 401, (
        "Şifre değişti ama ESKİ access token hâlâ geçerli — oturum sözleşmesi kırık"
    )


def test_her_giris_yeni_kimlik_uretir(ortam):
    """Fixation'ın yapısal karşılığı: token giriş anında ÜRETİLİR, önceden bilinemez."""
    import jwt as _jwt
    c, _ = ortam
    _kayit(c)
    ilk = c.post("/api/auth/login", json={"email": "oturum@example.com",
                                          "password": "Gucluu-Parolam-2026!"}).json()
    ikinci = c.post("/api/auth/login", json={"email": "oturum@example.com",
                                             "password": "Gucluu-Parolam-2026!"}).json()
    j1 = _jwt.decode(ilk["access_token"], options={"verify_signature": False})
    j2 = _jwt.decode(ikinci["access_token"], options={"verify_signature": False})
    assert j1["jti"] != j2["jti"], "İki giriş AYNI kimliği üretti (fixation yüzeyi)"
