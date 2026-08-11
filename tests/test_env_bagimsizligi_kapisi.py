"""
BUG #286 — SÜİT, GELİŞTİRİCİNİN `.env`'İNDEN BAĞIMSIZ OLMALI.

ÖLÇÜLEN DEFEKT (11 Ağu 2026): kapalı beta yayına alınırken `.env`'e
`REGISTRATION_MODE=invite_only` yazıldı ve süit **anında kırmızıya döndü**
(`tests/auth/test_auth.py::test_register_basarili_token_doner`). Sebep: `app/database.py`
import anında `load_dotenv()` çağırır; `.env` ortamda olmayan her anahtarı **doldurur**.
Yani süitin sonucu, **repoda olmayan bir dosyaya** bağlıydı — aynı commit iki makinede
farklı sonuç verebiliyordu.

`conftest.py`'de bunu engellemek için bir koruma ZATEN vardı ("Testler .env'e BAĞLI
OLMAMALI") ama **kapsamı tahminle kurulmuştu**: yalnız `AUTH_ENABLED` ve `ENVIRONMENT`
sayılıyordu. Koruma var, kapsamı ölçülmemiş — bu projede en az beş kez tekrar eden sınıf
(L11/H25).

Bu kapı kapsamı KAYNAKTAN doğrular: davranış değiştiren bir env okuması eklenip
`DAVRANIS_DEGISTIREN_ENV`'e yazılmazsa burası kırmızıya döner.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from tests.conftest import DAVRANIS_DEGISTIREN_ENV, TEST_ENV_SABITLERI

KOK = Path(__file__).resolve().parent.parent
APP = KOK / "app"

# Davranış değiştiren env okumalarının BULUNDUĞU modüller. Buradaki her `os.getenv("X")`
# ya nötrlenmiş listede olmalı ya da aşağıda gerekçesiyle muaf sayılmalı.
IZLENEN_MODULLER = ("settings.py", "beta_access.py", "spa.py")

# Muafiyetler — her biri NEDEN test sonucunu değiştirmediğiyle birlikte.
MUAF = {
    # Sır/bağlantı: testler kendi DB'sini ve anahtarını zaten kurar; `.env`'deki değer
    # test sonucunu değiştirmez (fixture'lar override eder).
    "SECRET_KEY", "DATABASE_URL",
    # Sayısal ayarlar: varsayılanları test edilen davranışı değiştirmiyor.
    "SAFE_DEBT_BUFFER", "ACCESS_TTL_MIN", "REFRESH_TTL_DAYS",
    # Kayıt/oturum dışı operasyonel ayarlar.
    "LOG_LEVEL", "LOG_DIR", "LOG_ROTATION_MAX_MB", "LOG_ROTATION_BACKUP",
    "CORS_ORIGINS", "TRUST_PROXY_HEADERS",
}
# NOT — MUAF listesi İKİ KEZ yanlış çıktı ve ikisini de kapı buldu:
#   `FRONTEND_URL` (CORS listesi) ve `SUPPORT_EMAIL` (kimliksiz künye). Tam da bu yüzden
#   kapsam elle yazılan bir listeye değil KAYNAK TARAMASINA bağlandı: "hangi anahtar
#   davranışı değiştirir?" sorusunu insan sezgisi güvenilir biçimde cevaplayamıyor.
#
# `FRONTEND_URL` bir zamanlar burada MUAF sayılıyordu — YANLIŞTI. `.env`'de ts.net
# adresine çevrildiği an `test_cors_izinli_origin_yansitilir` kırmızıya döndü, çünkü
# production'da CORS listesi YALNIZ FRONTEND_URL'den kurulur (BUG #178). Muafiyet
# gevşetilmedi, KALDIRILDI ve anahtar sabitlenenler listesine alındı (L51: kapı
# yanlış-pozitif verdiğinde ölçüleni kapıya uydurma, kapıyı kesinleştir).


def _env_okumalari(dosya: Path) -> set[str]:
    """`os.getenv("X")` / `os.environ.get("X")` çağrılarındaki sabit anahtarlar."""
    bulunan: set[str] = set()
    agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
    for d in ast.walk(agac):
        if not isinstance(d, ast.Call) or not d.args:
            continue
        f = d.func
        ad = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
        if ad not in ("getenv", "get"):
            continue
        ilk = d.args[0]
        if isinstance(ilk, ast.Constant) and isinstance(ilk.value, str) and ilk.value.isupper():
            bulunan.add(ilk.value)
    return bulunan


def test_davranis_degistiren_env_listesi_KAYNAKTAN_dogrulanir():
    """Yeni bir davranış anahtarı eklenip nötrlenmezse bu kapı kırmızıya döner."""
    okunan: set[str] = set()
    for ad in IZLENEN_MODULLER:
        yol = APP / ad
        assert yol.exists(), f"İzlenen modül yok: {yol} — kapı ölçtüğünü bulamıyor"
        okunan |= _env_okumalari(yol)

    assert okunan, "Hiç env okuması bulunamadı — AST taraması çökmüş olabilir"

    kapsanmayan = okunan - set(DAVRANIS_DEGISTIREN_ENV) - MUAF
    assert not kapsanmayan, (
        "Bu env anahtarları uygulamanın davranışını değiştirebiliyor ama testlerde "
        f"nötrlenmiyor: {sorted(kapsanmayan)}.\n"
        "Ya `tests/conftest.py:DAVRANIS_DEGISTIREN_ENV`'e ekleyin ya da bu dosyadaki "
        "MUAF kümesine GEREKÇESİYLE yazın. Aksi halde geliştiricinin .env'i süitin "
        "sonucunu değiştirir (BUG #286)."
    )


@pytest.mark.parametrize("anahtar", sorted(TEST_ENV_SABITLERI))
def test_her_anahtar_TEST_DEGERINDE(anahtar):
    """conftest sabitlemesi fiilen çalışıyor mu — liste yazıp uygulamamak kolaydır."""
    assert os.getenv(anahtar) == TEST_ENV_SABITLERI[anahtar], (
        f"{anahtar} test ortamında beklenen değerde değil "
        f"({os.getenv(anahtar)!r} != {TEST_ENV_SABITLERI[anahtar]!r}) — "
        "conftest sabitlemesi çalışmıyor, .env sızıyor olabilir"
    )


def test_import_ANINDA_okunan_ayarlar_dogru_kurulmus():
    """Fixture'ın yetişemediği yer: modül seviyesinde hesaplanan CORS listesi.

    `.env`'de ENVIRONMENT=production varken bu liste YALNIZ FRONTEND_URL'i içerir
    (BUG #178) ve localhost testleri kırılır. Sabitleme app import'undan ÖNCE
    koşmazsa bu assert düşer.
    """
    from app.main import _cors_origins
    assert "http://localhost:5173" in _cors_origins, (
        f"CORS listesi .env'den etkilenmiş: {_cors_origins}"
    )


def test_kayit_modu_testte_ACIK_kabul_edilir():
    """Sözleşmenin uçtaki sonucu: `.env` invite_only olsa bile testler açık modda koşar.

    Bu, defektin KENDİSİNİ ölçer: `.env`'e `REGISTRATION_MODE=invite_only` yazıldığında
    kırmızıya dönen tam olarak buydu.
    """
    from app.beta_access import invite_required, registration_mode
    assert registration_mode() == "open"
    assert invite_required() is False


def test_spa_testte_KAPALI():
    """SERVE_SPA `.env`'de açıksa kök yol JSON yerine HTML dönerdi (BUG #284 testleri kırılır)."""
    from app.spa import spa_aktif
    assert spa_aktif() is False


def test_conftest_listesi_bos_degil():
    """Liste boşaltılırsa koruma sessizce ölür (kapsam tabanı)."""
    assert len(DAVRANIS_DEGISTIREN_ENV) >= 6
