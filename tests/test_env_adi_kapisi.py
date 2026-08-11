"""
ENV ADI KAPISI — BUG #297.

ÖLÇÜLEN DEFEKT: `tests/test_kapasite_kapisi.py` SMTP'yi yapılandırmak için
`SMTP_PASSWORD` set ediyordu; kod ise `SMTP_PASS` okuyor. Yani fixture'ın kurduğunu
sandığı ortam HİÇ KURULMUYORDU. Test yine de yeşildi — çünkü **geliştiricinin `.env`'inde
gerçek `SMTP_PASS` vardı** ve boşluğu o dolduruyordu. CI'da `.env` yok: `smtp_configured()`
False döndü, `send_email` kapasite yoluna hiç girmeden çıktı ve "bekleme süresi 0.00 sn"
ile kırmızı verdi.

Aynı yazım hatası üç testte daha vardı ve orada tersten zarar veriyordu: `delenv` ile
"SMTP kapalı" senaryosu kurmaya çalışan testler yanlış adı sildiği için SMTP'yi
KAPATAMIYORDU — o testler geliştirici makinesinde SMTP AÇIK hâlde koşuyordu.

DERS (L59): bir env adının yazımı, testin kurduğu dünyanın gerçek olup olmadığını
belirler; yanlış ad sessizdir (KeyError yok, uyarı yok) ve `.env`'i dolu olan makinede
gizlenir. Bu kapı, testlerin dokunduğu her env adının kodda GERÇEKTEN okunduğunu doğrular.

Kapsam notu: kapı yalnız `app/` içinde okunan adları gerçek sayar. Testin kendi icat
ettiği bir ad (fixture bayrağı vb.) beyaz listeye yazılır — beyaz liste büyüyorsa bu,
kuralın erimesi demektir; her giriş gerekçeli olmalıdır.
"""
from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

# Testin kendi icat ettiği ya da kodda DİNAMİK üretilen adlar. Her satır gerekçelidir;
# liste büyüyorsa kural eriyor demektir.
BEYAZ_LISTE = {
    "PG_TEST_URL",                    # tests/pg_gate.py — yalnız süitin kendi kapısı
    "FINANCIALOS_SUITE_DB_OVERRIDE",  # BUG #289 — izolasyon ölçüm aracının escape hatch'i
    "PLAYWRIGHT_BASE_URL", "E2E_API", "VITE_API_HEDEF", "VITE_OTOMATIK_AC",
    "PATH", "PYTHONPATH", "TZ", "HOME", "USERPROFILE",
}


def _dinamik_uretilen_adlar() -> set[str]:
    """`app/rate_limit.py` env adlarını f-string ile üretir: f"RATE_LIMIT_{bucket}_MAX".

    Tam literal kaynakta geçmediği için düz tarama onları "hayalet" sanır. Elle beyaz
    listeye yazmak yerine **kodun kendi bucket listesinden** türetiyoruz: böylece kapı
    hem yanlış pozitif üretmez hem de `RATE_LIMIT_YANLISAD_MAX` gibi gerçek bir yazım
    hatasını yakalamaya devam eder (o bucket `_DEFAULTS`'ta yoktur).
    """
    from app.rate_limit import _DEFAULTS
    return {f"RATE_LIMIT_{b.upper()}_{sonek}"
            for b in _DEFAULTS for sonek in ("MAX", "WINDOW")}

_ENV_DESENI = re.compile(
    r"""(?:monkeypatch\.(?:setenv|delenv)|os\.environ(?:\.pop)?)\s*\(\s*["']([A-Z][A-Z0-9_]{2,})["']"""
)
# Kod tarafında env adı YALNIZ `os.getenv("X")` biçiminde yaşamaz: `app/capacity.py`
# onları sözlük değeri olarak tutar (`EPOSTA: ("EPOSTA_MAX_CONCURRENCY", 2)`), auth
# ayarları da öyle. Bu yüzden kaynakta geçen TÜM büyük-harfli string sabitleri gerçek
# sayılır — soru "bu ad kodda var mı?"dır, "nasıl okunuyor?" değil.
_KOD_DESENI = re.compile(r"""["']([A-Z][A-Z0-9_]{2,})["']""")


def _kodda_okunan_adlar() -> set[str]:
    adlar: set[str] = set()
    for dizin in ("app", "scripts", "alembic"):
        for py in (KOK / dizin).rglob("*.py"):
            adlar |= set(_KOD_DESENI.findall(py.read_text(encoding="utf-8")))
    return adlar


def _testlerin_dokundugu_adlar() -> dict[str, list[str]]:
    kullanim: dict[str, list[str]] = {}
    for py in (KOK / "tests").rglob("*.py"):
        if py.name == "test_env_adi_kapisi.py":
            continue
        for ad in _ENV_DESENI.findall(py.read_text(encoding="utf-8")):
            kullanim.setdefault(ad, []).append(py.relative_to(KOK).as_posix())
    return kullanim


def test_testlerin_kullandigi_env_adlari_kodda_okunuyor():
    """Bir test var olmayan bir env adına dokunuyorsa, kurduğunu sandığı dünya sahtedir."""
    kodda = _kodda_okunan_adlar()
    assert len(kodda) > 20, "kod taraması çalışmadı (env okuması bulunamadı)"

    gecerli = kodda | BEYAZ_LISTE | _dinamik_uretilen_adlar()
    hayalet = {
        ad: yerler for ad, yerler in _testlerin_dokundugu_adlar().items()
        if ad not in gecerli
    }
    assert not hayalet, (
        "Testler kodda HİÇ okunmayan env adlarına dokunuyor — kurulan ortam sahte "
        "(BUG #297: `SMTP_PASSWORD` yazılmış, kod `SMTP_PASS` okuyordu):\n  "
        + "\n  ".join(f"{ad}: {', '.join(sorted(set(y)))}" for ad, y in sorted(hayalet.items()))
    )


def test_smtp_yapilandirmasi_kodla_ayni_adi_kullanir():
    """Ölçülen defektin doğrudan regresyon kilidi (kapı erirse bile bu kalır)."""
    email_kaynak = (KOK / "app" / "services" / "email.py").read_text(encoding="utf-8")
    assert 'os.getenv("SMTP_PASS"' in email_kaynak, "kodda SMTP şifresi adı değişmiş"

    for yol in ("tests/test_kapasite_kapisi.py",
                "tests/test_email_verification.py",
                "tests/security/test_auth_hardening_p2.py",
                "tests/security/test_refresh_rotation_password_policy_p2.py"):
        icerik = (KOK / yol).read_text(encoding="utf-8")
        assert "SMTP_PASSWORD" not in icerik, (
            f"{yol}: kodun okumadığı `SMTP_PASSWORD` adı geri gelmiş — "
            f"bu ad `.env`'i dolu olan makinede sessizce çalışıyor gibi görünür."
        )
