"""
BUG #245 (denetim D30) — ÖRNEK DOSYANIN PLACEHOLDER'I FAIL-FAST'İ GEÇİYORDU.

`.env.prod.example` git'te herkese açıktır ve operatör onu kopyalayarak `.env.prod` üretir.
`SECRET_KEY` için placeholder reddi (`"REPLACE" in secret`) VARDI; ama **aynı dosyadaki
diğer placeholder'lar için yoktu.** Kanıt (denetim, koşturularak): `ENVIRONMENT=production`
+ `SUPPORT_EMAIL='destek@<alan-adin>'` ile `validate_security_config()` **hatasız geçti** —
üstelik `scripts/live_gate.py` de `"@" in destek` diye baktığı için canlı kapı da yeşildi.

Zarar BUG #210'un kapatmaya çalıştığı zararın aynısıdır: giriş yapamayan kullanıcı (yanlış
şifre / doğrulanmamış e-posta / çalışmayan davet kodu) uygulama-içi geri bildirim widget'ına
da ulaşamaz; giriş ekranında ve `/api/meta`'da gösterilen tek kanal **teslim edilemeyen bir
adres** olur. Kullanıcı sessizce kaybedilir, KVKK'nın "veri sorumlusuna başvuru" hakkı fiilen
kullanılamaz hâle gelir — ve iki bağımsız otomatik kapı buna "geçti" der.

Kök düzeltme desen eklemek DEĞİL, kaynağı değiştirmek: placeholder'ın ne olduğunu **örnek
dosyanın kendisi** söyler. `.env.prod.example`'daki değerin aynısı canlıda kullanılamaz.
Böylece yarın örneğe yeni bir anahtar eklenirse kapı onu da kapsar (L26: sınıflandırmayı
tahmine değil kaynağa bağla).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.settings import (
    ORNEK_ENV_YOLU, ornek_env_degerleri, placeholder_mi,
    secret_key_problems, support_problems, validate_security_config,
)

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture
def prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("SUPPORT_EMAIL", "destek@gercekalan.com")
    return monkeypatch


# ============================================================
# 1. KAYNAK — placeholder tanımı örnek dosyadan gelir
# ============================================================

def test_ornek_dosya_okunabiliyor():
    """Kapsam tabanı: örnek dosya bulunamazsa kapı sessizce boşa düşer (L23)."""
    assert ORNEK_ENV_YOLU.exists(), f"Örnek env dosyası yok: {ORNEK_ENV_YOLU}"
    degerler = ornek_env_degerleri()
    assert len(degerler) >= 10, f"Örnek dosyadan yalnız {len(degerler)} anahtar okundu"
    assert "SUPPORT_EMAIL" in degerler and "SECRET_KEY" in degerler


@pytest.mark.parametrize("deger", [
    "REPLACE_WITH_python_secrets_token_urlsafe_48",
    "destek@<alan-adin>",
    "financialos.example.com",
    "changeme",
    "<alan-adin>",
])
def test_placeholder_taninir(deger):
    assert placeholder_mi(deger) is True, f"Placeholder tanınmadı: {deger!r}"


@pytest.mark.parametrize("deger", [
    "destek@financialos.com.tr",
    "kOxT9d2Jw1ZqL8vN3sB7yR5eA0uH6mP4iC2gF1kD9nX",
    "gercekalan.com",
])
def test_gercek_deger_placeholder_sayilmaz(deger):
    """L6: kapı ürünü kıramaz — gerçek değerler reddedilmemeli."""
    assert placeholder_mi(deger) is False, f"Gerçek değer placeholder sayıldı: {deger!r}"


# ============================================================
# 2. DAVRANIŞ — fail-fast placeholder'ı reddeder
# ============================================================

def test_support_email_placeholder_reddedilir(prod):
    prod.setenv("SUPPORT_EMAIL", "destek@<alan-adin>")
    sorunlar = support_problems()
    assert sorunlar, "Placeholder destek adresi fail-fast'i geçti (D30)"
    assert "placeholder" in " ".join(sorunlar).lower()


def test_gercek_support_email_gecer(prod):
    assert support_problems() == []


def test_secret_key_placeholder_hala_reddedilir(prod):
    """Regresyon: BUG #210/MA3 koruması ortak yardımcıya taşınırken kaybolmasın."""
    prod.setenv("SECRET_KEY", "REPLACE_WITH_python_secrets_token_urlsafe_48")
    assert secret_key_problems(), "SECRET_KEY placeholder'ı artık reddedilmiyor"


def test_validate_security_config_placeholder_da_patlar(prod):
    prod.setenv("SUPPORT_EMAIL", "destek@<alan-adin>")
    with pytest.raises(RuntimeError, match="(?i)placeholder"):
        validate_security_config()


def test_development_ortaminda_bloklanmaz(monkeypatch):
    """Yerel geliştirici örnek dosyayla çalışabilmeli (fail-fast yalnız production)."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("SUPPORT_EMAIL", "destek@<alan-adin>")
    assert support_problems() == []


# ============================================================
# 3. CANLI KAPI da aynı gerçeği ölçer
# ============================================================

def test_live_gate_placeholder_i_yesil_gecmez():
    """Aynı boşluk canlı kapıda da vardı: `"@" in destek` placeholder'ı geçiriyordu."""
    kaynak = (KOK / "scripts" / "live_gate.py").read_text(encoding="utf-8")
    assert "placeholder_mi" in kaynak, (
        "live_gate destek adresini hâlâ '@ var mı' ile ölçüyor — placeholder yeşil geçer"
    )


def test_ornek_dosyadaki_her_zorunlu_anahtar_kapiya_bagli():
    """Kapsam kilidi: örnek dosyada 'ZORUNLU' diye işaretlenen her anahtar için
    fail-fast'te bir kontrol olmalı — aksi halde yeni bir zorunlu anahtar sessizce
    placeholder'la canlıya çıkar."""
    metin = ORNEK_ENV_YOLU.read_text(encoding="utf-8")
    zorunlular = {m.group(1) for m in re.finditer(r"^([A-Z_]+)=.*ZORUNLU", metin, re.M)}
    ayarlar = (KOK / "app" / "settings.py").read_text(encoding="utf-8")
    eksik = [a for a in zorunlular if a not in ayarlar]
    assert zorunlular, "Örnek dosyada 'ZORUNLU' işaretli anahtar bulunamadı — tarama bozuk"
    assert not eksik, f"Örnekte ZORUNLU denen ama fail-fast'te kontrolü olmayan anahtarlar: {eksik}"
