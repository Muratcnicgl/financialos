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

GUNCELLEMELER
-------------
BUG #304 fix: kapı TEK YÖNLÜYDÜ. Yalnız "test → kod" eksenine bakıyordu; oysa aynı
sessiz-yazım-hatası sınıfının ikinci yarısı **operatörün gördüğü belgede** yaşıyor.
Ölçüm iki yönde de canlı defekt buldu:

  (a) ÖLÜ AD — `.env.example` `AUTH_RATE_MAX=10` ve `AUTH_RATE_WINDOW=60` ilan ediyordu;
      kod bu iki adı HİÇ okumuyor (gerçekleri `RATE_LIMIT_LOGIN_MAX/_WINDOW`, aynı
      dosyanın 30 satır aşağısında). Bu ikili zaten BUG #297'nin metninde geçiyor
      (PROJE.md) — yani sorun BİLİNİYORDU, kapı o yönü kapatmıyordu. Zararı sessiz ve
      tek yönlü değil: `AUTH_RATE_MAX=100` yazan operatör rate-limit'i gevşettiğini
      sanır, kod varsayılan 5'te kalır — yani belge, YAPILMAMIŞ bir yapılandırmayı
      YAPILMIŞ gösterir.

  (b) BELGESİZ AD — `app/` içinde `os.getenv` ile okunan 24 anahtar iki örnek dosyanın
      hiçbirinde yoktu. Aralarında `SERVE_SPA` de vardı: açıkken `frontend/dist` yoksa
      `app/spa.py` bilerek fail-fast eder ve **uygulama hiç açılmaz**. Yani operatörün
      elindeki tek şema, uygulamayı açtırmayan anahtardan hiç söz etmiyordu.

L63: bir env adının iki tarafı vardır — kodun okuduğu ve belgenin vaat ettiği. İkisi
ayrı ayrı doğru olabilir ve yine de sistem yalan söyler; kapı ikisini de bağlamalıdır.
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


# ============================================================
# BUG #304 — KAPININ İKİNCİ YÖNÜ: ÖRNEK DOSYA ↔ KOD
# ============================================================

ORNEK_DOSYALAR = (".env.example", ".env.prod.example")

# Bir env adı Python'da okunmadan da GERÇEK olabilir: compose onu konteynere geçirir,
# Caddy şablonunda kullanır, entrypoint export eder. `DOMAIN`, `TZ`, `POSTGRES_PASSWORD`,
# `WEB_CONCURRENCY`, `BACKUP_*` tam olarak böyle yaşar — bu dosyalar taranmazsa kapı
# onları "ölü" sanıp yanlış pozitif üretir.
ALTYAPI_DOSYALARI = (
    "docker-compose.yml", "docker-compose.prod.yml", "Dockerfile", "Dockerfile.web",
    "Caddyfile", "docker-entrypoint.sh", ".github/workflows/ci.yml",
)

# `.env` örneğinde anahtar satırı: `AD=` ya da yorumlanmış `# AD=` (ikincisi de belgedir —
# `# DATABASE_URL=sqlite:////data/financialos.db` operatöre adı VE biçimi söyler).
_ORNEK_ANAHTAR_DESENI = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]{2,})\s*=")

# Yalnız GERÇEK okuma. Buradaki soru artık "bu ad kodda geçiyor mu" değil, "uygulama bu
# adı ortamdan OKUYOR mu" — yani `_KOD_DESENI`nin gevşekliği bu yönde kabul edilemez
# (her büyük harfli dizge sabiti sayılsaydı "GET", "POST" da env sanılırdı).
_OKUMA_DESENI = re.compile(
    r"""os\.(?:getenv|environ\.get|environ\.pop)\(\s*["']([A-Z][A-Z0-9_]{2,})["']"""
    r"""|os\.environ\[\s*["']([A-Z][A-Z0-9_]{2,})["']"""
)


def _ornek_dosya_adlari() -> dict[str, list[str]]:
    """Örnek `.env` dosyalarının ilan ettiği anahtar → hangi dosyalarda geçtiği."""
    kullanim: dict[str, list[str]] = {}
    for dosya in ORNEK_DOSYALAR:
        p = KOK / dosya
        if not p.exists():
            continue
        for satir in p.read_text(encoding="utf-8").splitlines():
            m = _ORNEK_ANAHTAR_DESENI.match(satir)
            if m:
                kullanim.setdefault(m.group(1), []).append(dosya)
    return kullanim


def _altyapida_gecen_adlar() -> set[str]:
    adlar: set[str] = set()
    yollar = [KOK / ad for ad in ALTYAPI_DOSYALARI]
    deploy = KOK / "deploy"
    if deploy.is_dir():
        yollar += [p for p in deploy.rglob("*") if p.is_file()]
    for p in yollar:
        if p.is_file():
            adlar |= set(re.findall(r"[A-Z][A-Z0-9_]{2,}",
                                    p.read_text(encoding="utf-8", errors="replace")))
    return adlar


def _app_icinde_okunan_adlar() -> dict[str, list[str]]:
    """`app/` içinde ortamdan GERÇEKTEN okunan adlar → onları okuyan dosyalar."""
    kullanim: dict[str, list[str]] = {}
    for py in (KOK / "app").rglob("*.py"):
        for a, b in _OKUMA_DESENI.findall(py.read_text(encoding="utf-8")):
            kullanim.setdefault(a or b, []).append(py.relative_to(KOK).as_posix())
    return kullanim


def test_ornek_env_dosyalarindaki_her_ad_gercekten_okunuyor():
    """Belgenin vaat ettiği anahtar hiçbir yerde okunmuyorsa, belge YALAN SÖYLÜYOR.

    Ölçülen defekt (BUG #304a): `AUTH_RATE_MAX` / `AUTH_RATE_WINDOW`. Bu sınıfın zararı
    "dağınıklık" değil: operatör bir güvenlik ayarını değiştirdiğini sanır, hiçbir şey
    değişmez ve **hiçbir hata da çıkmaz**.
    """
    gecerli = _kodda_okunan_adlar() | _altyapida_gecen_adlar() | _dinamik_uretilen_adlar()
    olu = {
        ad: dosyalar for ad, dosyalar in _ornek_dosya_adlari().items()
        if ad not in gecerli
    }
    assert not olu, (
        "Örnek `.env` dosyaları, hiçbir yerde okunmayan anahtarlar ilan ediyor — "
        "operatör bunları ayarlar ve hiçbir şey değişmez (BUG #304a: `AUTH_RATE_MAX` "
        "yazılmış, kod `RATE_LIMIT_LOGIN_MAX` okuyordu):\n  "
        + "\n  ".join(f"{ad}: {', '.join(sorted(set(d)))}" for ad, d in sorted(olu.items()))
    )


def test_app_icinde_okunan_her_ad_ornek_dosyada_belgeli():
    """Uygulamanın davranışını değiştiren bir anahtar operatörün şemasında yoksa, yoktur.

    Ölçülen defekt (BUG #304b): `SERVE_SPA` iki örnek dosyanın da dışındaydı — açıkken
    derlenmiş arayüz yoksa `app/spa.py` bilerek fail-fast eder ve uygulama HİÇ AÇILMAZ.

    Kapsam bilinçli olarak `app/`: `scripts/` altındakiler geliştirme/operasyon
    araçlarının kendi bayraklarıdır (`PG_GATE_DATADIR`, `REHEARSAL_PORT`,
    `SETUP_DATA_FORCE`, `MIGRATION_DATABASE_URL`), operatörün `.env`'ine girmez.
    Bir ad bu kapıdan kaçmak için `app/`den `scripts/`e taşınırsa kural erimiş olur —
    o taşımanın gerekçesi ayrıca yazılmalıdır.
    """
    belgeli = set(_ornek_dosya_adlari())
    belgesiz = {
        ad: dosyalar for ad, dosyalar in _app_icinde_okunan_adlar().items()
        if ad not in belgeli
    }
    assert not belgesiz, (
        "`app/` bu env adlarını okuyor ama örnek `.env` dosyalarının hiçbiri onlardan "
        "söz etmiyor — operatör davranışı değiştiren bir anahtarı göremez "
        "(BUG #304b: `SERVE_SPA` belgesizdi ve yanlış kurulumda uygulamayı hiç "
        "açtırmıyordu):\n  "
        + "\n  ".join(f"{ad}: {', '.join(sorted(set(d)))}"
                      for ad, d in sorted(belgesiz.items()))
    )
