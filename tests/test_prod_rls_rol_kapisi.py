"""
PROD RLS ROL KAPISI — denetim D22 (BUG #238).

NEDEN (denetimin kanıtı, disk):
  1. `docker-compose.prod.yml` uygulamayı `postgresql://financialos:...@db` ile bağlıyordu ve
     satır 53 "RLS'in etkili olması için app NON-superuser rol (financialos) ile bağlanır"
     diyordu. Ama `financialos` aynı dosyada `POSTGRES_USER` — postgres:16-alpine'da bootstrap
     kullanıcısı **SUPERUSER**'dır ve superuser `FORCE ROW LEVEL SECURITY`'ye rağmen RLS'i
     bypass eder. Yani ADR-038/M51'in "DB-katmanı 2. savunma" beyanı prod'da FİİLEN YOKTU.
  2. Dual-dialect/RLS kapıları hiçbir otomatik ortamda koşmuyordu (CI'da postgres servisi ve
     `PG_TEST_URL` yok) → policy düşse veya FORCE kalksa hiçbir test kırmızı olmazdı.

Bu dosya iki iddiayı da statik kapıya bağlar (L17: "uygulandı" diyen belge en tehlikeli haliyle
yarım kalmış olabilir → iddiayı ölçen kapı yaz). Kapsam tabanı assert'li (L11): kapı hiçbir
servis/iş bulamadığı için "yeşil" görünemez.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

KOK = Path(__file__).resolve().parent.parent
COMPOSE = KOK / "docker-compose.prod.yml"
ENTRYPOINT = KOK / "docker-entrypoint.sh"
CI = KOK / ".github" / "workflows" / "ci.yml"
PROVISION = KOK / "scripts" / "provision_app_role.py"
ENV_ORNEK = KOK / ".env.prod.example"

# Uygulama trafiğini taşıyan servisler (migration YAPMAZLAR — scheduler hiç, web yalnız
# ayrı MIGRATION_DATABASE_URL ile). Bunlar RLS'e TABİ olmak zorunda.
UYGULAMA_SERVISLERI = ("backend", "scheduler")

_PG_PARCA = re.compile(r"postgres(?:ql)?://(?P<kullanici>[^:/@\s]+):(?P<sifre>[^@\s]+)@")
_INTERP = re.compile(r"\$\{(\w+)(?::-(?P<varsayilan>[^}]*))?(?::\?[^}]*)?\}")


def _coz(deger: str) -> str:
    """compose interpolasyonunu çöz: `${V:-x}`→`x` (operatör set etmezse fiilen kullanılan
    değer), `${V}`/`${V:?...}`→`ENV_V` (adı korunur, URL ayracı içermez)."""
    def _rep(m: re.Match) -> str:
        return m.group("varsayilan") if m.group("varsayilan") is not None else f"ENV_{m.group(1)}"
    return _INTERP.sub(_rep, deger or "")


def _pg_kullanici(url: str) -> str | None:
    m = _PG_PARCA.search(_coz(url))
    return m.group("kullanici") if m else None


def _pg_sifre(url: str) -> str | None:
    m = _PG_PARCA.search(_coz(url))
    return m.group("sifre") if m else None


@pytest.fixture(scope="module")
def compose() -> dict:
    assert COMPOSE.exists(), "docker-compose.prod.yml bulunamadı"
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def servisler(compose) -> dict:
    return compose.get("services") or {}


@pytest.fixture(scope="module")
def bootstrap_superuser(servisler) -> str:
    """postgres imajının `POSTGRES_USER`'ı = cluster'ın bootstrap SUPERUSER'ı."""
    db = servisler.get("db") or {}
    kullanici = (db.get("environment") or {}).get("POSTGRES_USER")
    assert kullanici, "db servisinde POSTGRES_USER yok — kapı ölçecek bir şey bulamadı"
    return str(kullanici)


# ── Kapsam tabanı (L11): kapı gerçekten bir şey ölçüyor mu? ───────────────────────────────

def test_kapsam_tabani_uygulama_servisleri_postgres_url_tasiyor(servisler, bootstrap_superuser):
    """Kapı boş kümede yeşil görünemesin: her uygulama servisinde postgres DATABASE_URL olmalı."""
    bulunan = []
    for ad in UYGULAMA_SERVISLERI:
        assert ad in servisler, f"'{ad}' servisi compose'dan kaybolmuş — kapı kapsamı daraldı"
        url = (servisler[ad].get("environment") or {}).get("DATABASE_URL", "")
        assert _pg_kullanici(url), f"{ad}: postgres DATABASE_URL okunamadı ({url!r})"
        bulunan.append(ad)
    assert len(bulunan) >= 2, "kapsam tabanı: en az 2 uygulama servisi ölçülmeli"


# ── ÇEKİRDEK: uygulama rolü superuser OLAMAZ (yoksa RLS diye bir savunma yok) ──────────────

@pytest.mark.parametrize("servis", UYGULAMA_SERVISLERI)
def test_uygulama_rolu_bootstrap_superuser_degil(servisler, bootstrap_superuser, servis):
    """D22: superuser FORCE'a rağmen RLS'i bypass eder → app rolü bootstrap kullanıcı OLAMAZ."""
    url = (servisler[servis].get("environment") or {}).get("DATABASE_URL", "")
    kullanici = _pg_kullanici(url)
    assert kullanici != bootstrap_superuser, (
        f"{servis} veritabanına '{kullanici}' ile bağlanıyor; bu postgres imajının "
        f"POSTGRES_USER'ı yani BOOTSTRAP SUPERUSER'ı. Superuser RLS'i (FORCE dahil) bypass eder → "
        "ADR-038/M51'in 'DB-katmanı 2. savunma' beyanı prod'da fiilen yok."
    )


def test_migration_ayri_sahip_rolu_ile_kosar(servisler, bootstrap_superuser):
    """App rolü DDL yapamaz; migration şema sahibi (bootstrap) rolüyle koşmalı — web servisinde."""
    ortam = servisler["backend"].get("environment") or {}
    migr = ortam.get("MIGRATION_DATABASE_URL", "")
    assert _pg_kullanici(migr) == bootstrap_superuser, (
        "backend'de MIGRATION_DATABASE_URL şema sahibi rolüyle tanımlı olmalı — aksi halde "
        "`alembic upgrade head` yetkisiz rolle koşar ve deploy şema değişikliğinde düşer."
    )


def test_scheduler_migration_kosmaz(servisler):
    """Şemayı yalnız web servisi migrate eder (MA4); scheduler'a sahip-rol sızdırılmamalı."""
    ortam = servisler["scheduler"].get("environment") or {}
    assert "MIGRATION_DATABASE_URL" not in ortam, (
        "scheduler migration koşmaz (docker-entrypoint.sh scheduler modu) — sahip rolünü "
        "taşıması gereksiz yetki yüzeyidir."
    )


def test_yedek_servisi_sahip_rolu_kullanir(servisler, bootstrap_superuser):
    """pg_dump RLS'e takılmamalı: yedek şema sahibi/superuser rolüyle alınır (eksik yedek riski)."""
    ortam = (servisler.get("backup") or {}).get("environment") or {}
    assert str(ortam.get("PGUSER")) == bootstrap_superuser, (
        "yedek servisi app rolüne düşürülmüş — RLS bağlamı sızarsa dump EKSİK satırla "
        "tamamlanır ve bunu kimse fark etmez."
    )


# ── Rol gerçekten var mı: provizyon yolu ──────────────────────────────────────────────────

def test_uygulama_rolu_provizyon_ediliyor(servisler, bootstrap_superuser):
    """Compose'daki app rolü havadan var olmaz — deploy yolunda idempotent yaratılmalı."""
    assert PROVISION.exists(), "scripts/provision_app_role.py yok — app rolü hiç yaratılmıyor"
    kaynak = PROVISION.read_text(encoding="utf-8")
    assert "NOSUPERUSER" in kaynak, "app rolü NOSUPERUSER olarak yaratılmıyor → RLS yine bypass"

    url = (servisler["backend"].get("environment") or {}).get("DATABASE_URL", "")
    rol = _pg_kullanici(url)
    assert rol and rol != bootstrap_superuser
    assert rol in kaynak, f"compose '{rol}' rolüyle bağlanıyor ama provizyon scripti onu yaratmıyor"

    ep = ENTRYPOINT.read_text(encoding="utf-8")
    assert "provision_app_role" in ep, (
        "docker-entrypoint.sh app rolünü provizyon etmiyor → ilk deploy'da uygulama "
        "'role does not exist' ile açılmaz (veya operatör elle superuser'a döner)."
    )


def test_env_ornegi_app_rol_sifresini_istiyor(servisler):
    """Operatör `APP_DB_PASSWORD`'ü doldurmazsa fail-fast olmalı; şablon bunu söylemeli."""
    url = (servisler["backend"].get("environment") or {}).get("DATABASE_URL", "")
    sifre = _pg_sifre(url)
    assert sifre and sifre.startswith("ENV_"), (
        f"app rolünün şifresi env'den GELMİYOR (gömülü/varsayılan olabilir): {url!r}"
    )
    degisken = sifre[len("ENV_"):]
    metin = ENV_ORNEK.read_text(encoding="utf-8")
    assert re.search(rf"^{degisken}=", metin, re.M), (
        f"{degisken} .env.prod.example'da yok → operatör tanımsız bırakır"
    )
    assert f"{degisken}:?" in url, (
        f"{degisken} compose'da zorunlu (`:?`) değil → boş şifreyle sessizce ayağa kalkar"
    )


# ── CI kapısı: dual-dialect/RLS testleri otomatik ortamda GERÇEKTEN koşuyor mu? ────────────

@pytest.fixture(scope="module")
def ci() -> dict:
    assert CI.exists(), ".github/workflows/ci.yml yok"
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def test_kapsam_tabani_dual_dialect_testleri_var():
    """Kapsam tabanı: pg gate'ine bağlı test dosyaları gerçekten mevcut (kapı boşa ölçmesin)."""
    dosyalar = [p for p in (KOK / "tests").glob("test_*.py")
                if "postgres_url_or_skip" in p.read_text(encoding="utf-8")]
    assert len(dosyalar) >= 4, f"dual-dialect test dosyası beklenenden az: {dosyalar}"


def test_ci_postgres_servisi_ile_kosuyor(ci):
    """D22: postgres servisi + PG_TEST_URL olmadan bu kapılar CI'da SKIP'e düşer (sessiz)."""
    isler = ci.get("jobs") or {}
    uygun = []
    for ad, is_ in isler.items():
        servisler_ = is_.get("services") or {}
        pg_var = any("postgres" in str(s.get("image", "")) for s in servisler_.values())
        adimlar = is_.get("steps") or []
        pg_url = any("PG_TEST_URL" in str(a.get("env") or {}) for a in adimlar)
        if pg_var and pg_url:
            uygun.append(ad)
    assert uygun, (
        "hiçbir CI işi postgres servisi + PG_TEST_URL ile koşmuyor → RLS/Numeric/NULL-ordering "
        "kapıları her koşumda SKIP; policy düşse kimse görmez."
    )


def test_ci_pg_kosumu_tum_suiti_kapsar(ci):
    """Dosya listesi tutulmasın (drift): PG_TEST_URL'li iş `tests/` dizininin tamamını koşmalı."""
    isler = ci.get("jobs") or {}
    for is_ in isler.values():
        for adim in (is_.get("steps") or []):
            if "PG_TEST_URL" not in str(adim.get("env") or {}):
                continue
            komut = str(adim.get("run") or "")
            assert re.search(r"pytest\s+tests/(\s|$)", komut), (
                "PG_TEST_URL'li adım tüm süiti koşmalı (`pytest tests/`) — elle tutulan dosya "
                f"listesi yeni dual-dialect testini sessizce dışarıda bırakır: {komut!r}"
            )
            return
    pytest.fail("PG_TEST_URL'li adım bulunamadı")
