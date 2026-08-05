"""
D06 (BUG #227) — BELGELENMİŞ BİR DAĞITIM YOLU KİMLİKSİZ CANLI SUNUCU ÜRETİYORDU.

`docs/deployment/README.md` iki yolu da resmî belgeliyor (ADR-035: systemd "alternatif").
Her ikisi de `cp .env.example .env` diyor; `.env.example` ise `ENVIRONMENT=development` ve
`AUTH_ENABLED=` (BOŞ). Yol 1'i (Docker) compose'un `${ENVIRONMENT:-production}` /
`${AUTH_ENABLED:-true}` varsayılanları kurtarıyordu; **Yol 2'de (systemd) hiçbir koruma yoktu.**

Denetimin çalıştırdığı kanıt (ENVIRONMENT=development + AUTH_ENABLED=""):
  validate_security_config() → İSTİSNA YOK (uygulama açılır)
  GET /api/cockpit → 200 · GET /api/accounts → 200 · GET /api/users/me/export → 200
  DELETE /api/users/me → 204        ← hepsi Authorization header OLMADAN

BUG #171 tam olarak bu senaryo için açılmış ve "kapatıldı" denmişti; koruma
`is_production()`e — yani unutulması en kolay değişkene — bağlı olduğu için bu yolda hiç
devreye girmiyordu (L8: belgelenen ≠ uygulanan).

Kök düzeltme doküman değil KOD: **güvenlik varsayılanı fail-CLOSED olmalı.** `AUTH_ENABLED`
tanımsız/boş/anlamsız ise kimlik doğrulama AÇIK sayılır; kapatmak için operatörün AÇIKÇA
`AUTH_ENABLED=false` yazması gerekir. Bu dosya o değişmezi, hangi dokümanın izlendiğinden
bağımsız olarak kilitler.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import auth as _auth
from app.settings import validate_security_config

KOK = Path(__file__).resolve().parent.parent.parent


# ============================================================
# 1. VARSAYILAN FAIL-CLOSED
# ============================================================

@pytest.mark.parametrize("deger", [None, "", "   "])
def test_auth_tanimsizsa_acik_sayilir(monkeypatch, deger):
    """Değişken unutulduğunda API kimliksiz AÇILMAMALI."""
    if deger is None:
        monkeypatch.delenv("AUTH_ENABLED", raising=False)
    else:
        monkeypatch.setenv("AUTH_ENABLED", deger)
    assert _auth.auth_enabled() is True, (
        "AUTH_ENABLED tanımsızken kimlik doğrulama KAPALI sayıldı — "
        "değişkeni unutan her kurulum tüm API'yi kimliksiz açar"
    )


@pytest.mark.parametrize("deger", ["belki", "sonra", "yes-please", "2"])
def test_anlamsiz_deger_acik_sayilir(monkeypatch, deger):
    """Yazım hatası güvenliği kapatmamalı (fail-closed)."""
    monkeypatch.setenv("AUTH_ENABLED", deger)
    assert _auth.auth_enabled() is True, f"{deger!r} değeri kimlik doğrulamayı kapattı"


@pytest.mark.parametrize("deger", ["0", "false", "False", "no", "off"])
def test_acik_kapatma_hala_mumkun(monkeypatch, deger):
    """Yerel tek-kullanıcı kurulumu AÇIKÇA kapatabilmeli (L6: geliştirmeyi kilitleme)."""
    monkeypatch.setenv("AUTH_ENABLED", deger)
    assert _auth.auth_enabled() is False, f"{deger!r} ile açık kapatma çalışmıyor"


@pytest.mark.parametrize("deger", ["1", "true", "TRUE", "yes"])
def test_acik_acma_calisir(monkeypatch, deger):
    monkeypatch.setenv("AUTH_ENABLED", deger)
    assert _auth.auth_enabled() is True


def test_production_acik_kapatmayi_da_reddeder(monkeypatch):
    """BUG #171 regresyonu: prod'da AÇIKÇA kapatmak da fail-fast olmalı."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("SUPPORT_EMAIL", "destek@ornek.com")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    with pytest.raises(RuntimeError, match="AUTH_ENABLED"):
        validate_security_config()


# ============================================================
# 2. DAĞITIM ŞABLONLARI — dokümanın söylediği şey gerçekten güvenli mi
# ============================================================

def _env_dosyasi_oku(yol: Path) -> dict:
    degerler = {}
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, _, deger = satir.partition("=")
        degerler[anahtar.strip()] = deger.split("#")[0].strip()
    return degerler


def _readme_sablonlari() -> list[str]:
    """Deployment README'nin `cp <sablon> .env` dediği tüm şablonlar."""
    metin = (KOK / "docs" / "deployment" / "README.md").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"cp\s+([\w./-]*\.env[\w.-]*)\s+\.env\b", metin)))


def test_readme_bir_env_sablonu_gosteriyor():
    """Kapsam tabanı (L11): regex hiçbir şey bulmuyorsa alttaki kapı sessizce boş koşar."""
    assert _readme_sablonlari(), \
        "Deployment README'de `cp <sablon> .env` satırı bulunamadı — kapı kör kalır"


def test_readme_deki_her_sablon_kimlikli_sunucu_uretir(monkeypatch):
    """Operatör dokümanı HARFİYEN izlerse kimliksiz sunucu ÇIKMAMALI (denetim D06)."""
    for sablon in _readme_sablonlari():
        yol = KOK / sablon
        assert yol.exists(), f"README var olmayan şablonu gösteriyor: {sablon}"
        degerler = _env_dosyasi_oku(yol)
        monkeypatch.setenv("AUTH_ENABLED", degerler.get("AUTH_ENABLED", ""))
        assert _auth.auth_enabled() is True, (
            f"{sablon} kopyalanınca kimlik doğrulama KAPALI kalıyor — bu şablonu izleyen "
            "operatör tüm finansal veriyi (cockpit/hesaplar/KVKK export/hesap silme) "
            "internete kimliksiz açar"
        )


def test_systemd_unit_kendini_production_ilan_eder():
    """Yol 2'de compose yok → `${ENVIRONMENT:-production}` yok. Unit kendisi söylemeli."""
    metin = (KOK / "deploy" / "financialos.service").read_text(encoding="utf-8")
    assert re.search(r"^Environment=ENVIRONMENT=production", metin, re.M), (
        "systemd unit'i ENVIRONMENT=production ilan etmiyor — prod sertleştirmeleri "
        "(fail-fast, /docs kapalı) bu yolda hiç devreye girmez"
    )
    # EnvironmentFile ÖNCE gelmeli: aksi halde eskimiş bir .env prod işaretini ezer.
    satirlar = [s.strip() for s in metin.splitlines()]
    i_dosya = next(i for i, s in enumerate(satirlar) if s.startswith("EnvironmentFile="))
    i_env = next(i for i, s in enumerate(satirlar) if s.startswith("Environment=ENVIRONMENT="))
    assert i_dosya < i_env, (
        "Environment=ENVIRONMENT=production, EnvironmentFile'dan ÖNCE geliyor — "
        ".env dosyasındaki eski `ENVIRONMENT=development` bunu sessizce ezer"
    )
