"""
D11 + D12 + D13/D09 (BUG #230) — PRODUCTION YIĞINI BELGELENEN KOMUTLA AYAĞA KALKMIYORDU
VE OTOMATİK YEDEĞİ YOKTU.

D11: `docker-compose.prod.yml`'de hiçbir serviste `env_file:` yoktu. Runbook'un tarif ettiği
tek deploy komutu `--env-file .env.prod` kullanıyor; o bayrak YALNIZ compose dosyasındaki
`${...}` interpolasyonunu besler, konteyner ortamına DEĞİŞKEN YAZMAZ. Sonuç: `.env.prod`'a
doğru yazılmış `SUPPORT_EMAIL` (BUG #210 gereği production'da ZORUNLU), `SMTP_*`, `OAUTH_*`,
`REGISTRATION_MODE`, `MAX_REQUEST_BODY_BYTES`, `COACH_DAILY_USER_LIMIT` konteynere hiç
ulaşmıyordu. Backend startup'ta fail-fast ile düşüyor, `deploy.sh` healthcheck'i geçemiyor ve
otomatik rollback aynı derecede bozuk önceki sürüme dönüyordu. Operatörün elinde "neden
açılmıyor" sorusunun cevabı yoktu — değeri yazmıştı ama uygulama onu hiç görmüyordu.
Operatör `SUPPORT_EMAIL`'i elle eklese bile davet/şifre-sıfırlama e-postası ve OAuth
SESSİZCE yapılandırılmamış kalıyordu.

D12: `scheduler` servisinde `AUTH_ENABLED` yoktu (backend'de açıkça vardı). 02:45 fiyat ve
03:00 gece batch'i hiç koşmuyordu → kullanıcı BAYAT fiyatlarla hesaplanmış net değere göre
para kararı veriyordu. Üstelik `deploy.sh` yalnız "UYARI: scheduler çalışmıyor" basıp
çıkış kodu 0 ile "TAMAM" diyordu.

D13/D09: Production yığınında OTOMATİK YEDEK yoktu. Beta kullanıcılarının tüm finansal
geçmişi tek bir Docker volume'unda, tek bir Free-Tier VM'de. Depodaki tek yedek otomasyonu
(`deploy/financialos-backup.service`) **SQLite-only** `scripts/backup.py`'yi çağırıyordu ve
Postgres URL'inde çıkış kodu 1 ile ölüyordu — operatör "timer kurdum" sanırken her gece
sessizce başarısız oluyordu.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

KOK = Path(__file__).resolve().parent.parent
COMPOSE = KOK / "docker-compose.prod.yml"
ORNEK_ENV = KOK / ".env.prod.example"

# Uygulamanın kendi ortamından okuduğu, .env.prod'da tarif edilen anahtarlar.
# (Compose'un `${...}` interpolasyonu bunları konteynere GEÇİRMEZ — env_file gerekir.)
_ORNEKTEN_GECMESI_GEREKENLER = [
    "SUPPORT_EMAIL",        # BUG #210: production'da zorunlu, yoksa uygulama başlamaz
    "REGISTRATION_MODE",    # kapalı beta anahtarı
    "SMTP_HOST",            # davet + şifre sıfırlama e-postası
    "OAUTH_GOOGLE_CLIENT_ID",
]


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def servisler(compose) -> dict:
    return compose["services"]


# ============================================================
# 1. KAPSAM TABANI (L11)
# ============================================================

def test_kapsam_tabani_servisler_bulunuyor(servisler):
    """Parse bozulursa alttaki kapılar sessizce boş koşar."""
    assert {"db", "backend", "scheduler", "web"} <= set(servisler), \
        f"Beklenen servisler bulunamadı: {sorted(servisler)}"


# ============================================================
# 2. D11 — .env.prod gerçekten konteynere ulaşıyor mu
# ============================================================

@pytest.mark.parametrize("servis", ["backend", "scheduler"])
def test_uygulama_servisleri_env_file_okur(servisler, servis):
    """`--env-file` yalnız interpolasyon içindir; konteyner ortamı için `env_file:` şart."""
    env_file = servisler[servis].get("env_file")
    assert env_file, (
        f"{servis} servisinde `env_file:` yok — .env.prod'daki değişkenler konteynere HİÇ "
        "ulaşmaz (operatör doğru yazsa bile uygulama görmez, D11)"
    )
    yollar = [env_file] if isinstance(env_file, str) else [
        e if isinstance(e, str) else e.get("path") for e in env_file
    ]
    assert any(".env.prod" in str(y) for y in yollar), \
        f"{servis} env_file .env.prod'u göstermiyor: {yollar}"


def test_ornekte_tarif_edilen_anahtarlar_fiilen_ulasiyor(servisler):
    """`.env.prod.example` bir anahtarı tarif ediyorsa uygulamaya ULAŞMALI (L8)."""
    ornek = ORNEK_ENV.read_text(encoding="utf-8")
    backend = servisler["backend"]
    acik_env = set(backend.get("environment") or {})
    env_file_var = bool(backend.get("env_file"))

    eksik = []
    for anahtar in _ORNEKTEN_GECMESI_GEREKENLER:
        if not re.search(rf"^{anahtar}=", ornek, re.M):
            continue  # örnek artık tarif etmiyorsa kapının konusu değil
        if anahtar not in acik_env and not env_file_var:
            eksik.append(anahtar)
    assert not eksik, (
        f".env.prod.example bu anahtarları tarif ediyor ama konteynere ulaşmıyorlar: {eksik}"
    )


# ============================================================
# 3. D12 — scheduler ile backend ortam pariteleri
# ============================================================

def test_scheduler_auth_enabled_tanimli(servisler):
    """Scheduler da aynı lifespan'i koşar; eksik AUTH_ENABLED crash-loop üretiyordu."""
    env = servisler["scheduler"].get("environment") or {}
    assert "AUTH_ENABLED" in env, (
        "scheduler servisinde AUTH_ENABLED yok — production fail-fast'i tetikler, "
        "cron hiç koşmaz ve kullanıcı bayat fiyatlarla karar verir (D12)"
    )
    assert str(env["AUTH_ENABLED"]).lower() in ("true", "1", "yes")


def test_scheduler_ve_backend_kritik_ortam_paritesi(servisler):
    """İki servis aynı uygulamayı koşar — güvenlik/ortam anahtarları ayrışmamalı."""
    b = set(servisler["backend"].get("environment") or {})
    s = set(servisler["scheduler"].get("environment") or {})
    kritik = {"ENVIRONMENT", "AUTH_ENABLED", "SECRET_KEY", "DATABASE_URL", "TZ"}
    eksik = sorted((kritik & b) - s)
    assert not eksik, f"scheduler'da eksik kritik ortam anahtarları: {eksik}"


# ============================================================
# 4. D13/D09 — otomatik yedek
# ============================================================

def test_prod_yiginda_otomatik_yedek_servisi_var(servisler):
    """Tek VM + tek volume: otomatik kopyası olmayan beta = geri dönülemez veri kaybı."""
    adaylar = [ad for ad in servisler if "backup" in ad or "yedek" in ad]
    assert adaylar, (
        "docker-compose.prod.yml'de otomatik yedek servisi yok — beta kullanıcılarının "
        "tüm finansal geçmişi tek volume'da, kopyasız (D13/D09)"
    )


def test_yedek_servisi_postgres_yedegi_alir(servisler):
    """SQLite script'i Postgres'te çıkış kodu 1 ile ölüyordu — yedek gerçekten alınmalı."""
    ad = next(a for a in servisler if "backup" in a or "yedek" in a)
    metin = yaml.safe_dump(servisler[ad])
    assert "pg_dump" in metin or "pg_backup" in metin, \
        f"{ad} servisi Postgres yedeği almıyor: {metin[:300]}"


def test_yedek_kalici_bir_hacimde_tutulur(compose, servisler):
    """Yedek konteyner katmanında kalırsa `docker compose down` ile birlikte yok olur."""
    ad = next(a for a in servisler if "backup" in a or "yedek" in a)
    hacimler = servisler[ad].get("volumes") or []
    tanimli = set(compose.get("volumes") or {})
    bagli = [str(v).split(":")[0] for v in hacimler]
    assert any(b in tanimli for b in bagli), (
        f"{ad} servisi adlandırılmış bir hacme yazmıyor ({bagli}) — yedekler kalıcı değil"
    )


def test_yedek_scripti_var_ve_saklama_suresi_uyguluyor():
    """Sonsuz biriken yedek Free-Tier diski doldurur → yeni yedek de alınamaz."""
    betik = KOK / "deploy" / "pg_backup.sh"
    assert betik.exists(), "deploy/pg_backup.sh yok"
    metin = betik.read_text(encoding="utf-8")
    assert "pg_dump" in metin
    assert "KEEP_DAYS" in metin or "keep-days" in metin, \
        "Yedek script'i saklama süresi (rotasyon) uygulamıyor"
    assert re.search(r"set -e", metin), "Script hata durumunda sessizce devam ediyor"


def test_bayat_sqlite_yedek_unitesi_postgresi_yanlis_yonlendirmiyor():
    """Depodaki systemd yedek unit'i SQLite-only script çağırıyordu (Postgres'te exit 1).

    Ya Postgres'i desteklemeli ya da hangi kurulum için olduğunu AÇIKÇA söylemeli —
    aksi halde operatör "yedeğim var" sanır (D09).
    """
    unit = (KOK / "deploy" / "financialos-backup.service").read_text(encoding="utf-8")
    assert re.search(r"SQLite|sqlite", unit), (
        "Yedek unit'i hangi veritabanı için olduğunu söylemiyor — Postgres kurulumda "
        "her gece sessizce başarısız olur"
    )
