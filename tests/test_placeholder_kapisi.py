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

def _live_gate_kaynak() -> str:
    return (KOK / "scripts" / "live_gate.py").read_text(encoding="utf-8")


def test_live_gate_placeholder_i_yesil_gecmez():
    """Aynı boşluk canlı kapıda da vardı: `"@" in destek` placeholder'ı geçiriyordu."""
    assert "placeholder" in _live_gate_kaynak(), (
        "live_gate destek adresini hâlâ '@ var mı' ile ölçüyor — placeholder yeşil geçer"
    )


def test_live_gate_uygulama_paketini_IMPORT_ETMEZ():
    """Canlı kapı BİLİNÇLİ olarak bağımsızdır: uygulama paketi olmayan bir makineden
    (operatörün dizüstü) canlı URL'ye karşı koşabilmeli.

    Bu test bir hatadan doğdu: placeholder ölçütü `from app.settings import placeholder_mi`
    ile eklendi ve script `ModuleNotFoundError: No module named 'app'` ile ÇÖKTÜ — yani
    "kapıyı sertleştiren" değişiklik kapıyı tamamen ÖLDÜRMÜŞTÜ ve bu ancak script GERÇEKTEN
    koşturulunca görüldü (R3: koşan komut > kod > doküman)."""
    import re as _re
    kaynak = _live_gate_kaynak()
    ihlaller = _re.findall(r"^\s*(?:from|import)\s+app[\s.]", kaynak, _re.M)
    assert not ihlaller, (
        f"live_gate.py uygulama paketini import ediyor ({ihlaller}) — script bağımsızlığını "
        "kaybeder ve app olmayan makinede ÇÖKER"
    )


def test_live_gate_deseni_settings_ile_ayni():
    """Desen iki yerde yaşıyor (import yerine kopya — yukarıdaki gerekçe). O hâlde
    AYRIŞMAMALARI teste bağlı olmalı: tek kaynak burada sözleşmedir, import değil."""
    import ast as _ast
    from app.settings import _PLACEHOLDER_IZLERI as ayarlardaki
    agac = _ast.parse(_live_gate_kaynak())
    bulunan = None
    for dugum in _ast.walk(agac):
        if isinstance(dugum, _ast.Assign) and any(
                getattr(h, "id", "") == "_PLACEHOLDER_IZLERI" for h in dugum.targets):
            bulunan = tuple(_ast.literal_eval(dugum.value))
    assert bulunan is not None, "live_gate'te _PLACEHOLDER_IZLERI bulunamadı"
    assert set(bulunan) == set(ayarlardaki), (
        f"Placeholder desenleri ayrışmış — live_gate={sorted(bulunan)}, "
        f"settings={sorted(ayarlardaki)}"
    )


def test_ornek_dosya_IMAJDA_YOKKEN_de_placeholder_yakalanir(monkeypatch, prod):
    """Prod imajında `.env.prod.example` BULUNMAYABİLİR (.dockerignore).

    Kapı yalnız "örnek dosyadaki değere eşit mi" diye baksaydı, tam da korumanın gerektiği
    yerde (canlı imaj) sessizce devre dışı kalırdı — bir kapının dev'de çalışıp prod'da
    çalışmaması, hiç olmamasından daha kötüdür (yanlış güven). Desen kontrolü bu yüzden
    örnek dosyadan BAĞIMSIZ da çalışır."""
    import app.settings as st
    gercek = st.ORNEK_ENV_YOLU
    monkeypatch.setattr(st, "ORNEK_ENV_YOLU", gercek.parent / "olmayan-dosya.example")
    st.ornek_env_degerleri.cache_clear()
    try:
        assert st.ornek_env_degerleri() == {}, "Dosya yokken sözlük boş olmalı"
        assert st.placeholder_mi("destek@<alan-adin>", "SUPPORT_EMAIL") is True
        assert st.placeholder_mi("destek@financialos.com.tr", "SUPPORT_EMAIL") is False
        monkeypatch.setenv("SUPPORT_EMAIL", "destek@<alan-adin>")
        with pytest.raises(RuntimeError, match="(?i)placeholder"):
            st.validate_security_config()
    finally:
        st.ornek_env_degerleri.cache_clear()


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
