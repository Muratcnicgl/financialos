"""
P3.5 (Wave-9) — BUG #169: prod konteynerlerinde SAAT DİLİMİ tanımlı değildi.

Sorun: `python:3.11-slim` konteyneri varsayılan **UTC** çalışır. Uygulama 19+ yerde
`date.today()` / yerel saat kullanıyor (günlük limit, işlem tarihi, "bugün harcadın",
zikzak devreden bakiye, cron gün sınırı). Türkiye UTC+3 olduğundan:

  - Gece 00:00–03:00 (TR) arasında girilen işlem BİR ÖNCEKİ güne yazılır.
  - "Bugünkü limit" yanlış güne ait hesaplanır.
  - "Gece 02:45" fiyat cron'u TR saatiyle 05:45'te koşar; "03:00 gece batch"i 06:00'da.
  - Ay sınırında (ayın 1'i, 00:00-03:00) düzenli gelir/gider tetikleme ayı kayar.

Yerel Windows geliştirmede görünmez (makine zaten TR). Yalnız DEPLOY'da ortaya çıkar →
kod testleri yakalayamaz. Bu yüzden kapı, deploy YAPILANDIRMASINI statik doğrular
(Blok A deseni: sunucu olmadan doğrulanabilen her şey doğrulanır).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

# Uygulama mantığı çalıştıran servisler (nginx/db değil — onlar saatten etkilenmiyor)
UYGULAMA_SERVISLERI = ("backend", "scheduler")


def _compose_metni() -> str:
    p = _ROOT / "docker-compose.prod.yml"
    assert p.exists(), "docker-compose.prod.yml yok"
    return p.read_text(encoding="utf-8")


def _servis_bloklari(metin: str) -> dict[str, str]:
    """Üst düzey servis adı → o servisin YAML bloğu (girintiye göre kaba ayrıştırma)."""
    bloklar: dict[str, str] = {}
    ad = None
    satirlar: list[str] = []
    for line in metin.splitlines():
        m = re.match(r"^  ([a-zA-Z0-9_-]+):\s*$", line)
        if m:
            if ad:
                bloklar[ad] = "\n".join(satirlar)
            ad = m.group(1)
            satirlar = []
        elif ad:
            satirlar.append(line)
    if ad:
        bloklar[ad] = "\n".join(satirlar)
    return bloklar


@pytest.mark.parametrize("servis", UYGULAMA_SERVISLERI)
def test_prod_serviste_saat_dilimi_tanimli(servis):
    """BUG #169: uygulama servisleri TZ olmadan çalışamaz (UTC → yanlış 'bugün')."""
    bloklar = _servis_bloklari(_compose_metni())
    assert servis in bloklar, f"docker-compose.prod.yml'de '{servis}' servisi yok"
    assert re.search(r"^\s*TZ:", bloklar[servis], re.MULTILINE), (
        f"'{servis}' servisinde TZ tanımlı değil → konteyner UTC çalışır ve "
        f"date.today() Türkiye'de gece yarısı–03:00 arası YANLIŞ gün verir."
    )


def test_dockerfile_tzdata_kurar():
    """TZ env'i işe yaraması için imajda zoneinfo veritabanı bulunmalı."""
    df = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "tzdata" in df, (
        "Dockerfile tzdata kurmuyor — TZ=Europe/Istanbul ayarlansa bile slim imajda "
        "zoneinfo verisi olmadan saat dilimi UTC'de kalır."
    )


def test_env_ornek_dosyasi_tz_belgeler():
    """Deploy eden kişi TZ'yi görmeli (varsayılan Europe/Istanbul)."""
    p = _ROOT / ".env.prod.example"
    assert p.exists()
    assert "TZ" in p.read_text(encoding="utf-8"), ".env.prod.example TZ'yi belgelemiyor"


# ══════════════════════════════════════════════════════════════════════════════
# BUG #182/#184 — proxy/limit/başlık yapılandırmasının statik kapısı
# (Sunucu olmadan doğrulanabilen her şey doğrulanır — Wave-8 Blok A deseni.)
# ══════════════════════════════════════════════════════════════════════════════

def test_backend_proxy_basliklarina_guvenir():
    """BUG #182: nginx önde olduğu için TRUST_PROXY_HEADERS açık olmalı.

    Kapalıysa limiter `request.client.host`u (= nginx IP'si) kullanır ve TÜM kullanıcılar
    tek rate-limit kovasına düşer: bir saldırgan herkesin girişini kilitler.
    """
    bloklar = _servis_bloklari(_compose_metni())
    assert re.search(r"^\s*TRUST_PROXY_HEADERS:", bloklar["backend"], re.MULTILINE), (
        "backend servisinde TRUST_PROXY_HEADERS yok → proxy arkasında rate limit tek kovaya düşer"
    )


def test_gunicorn_forwarded_ips_ayarli():
    """gunicorn varsayılanı 127.0.0.1'dir; nginx ayrı konteynerden gelir → başlık düşerdi."""
    entry = (_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "--forwarded-allow-ips" in entry, (
        "gunicorn --forwarded-allow-ips verilmiyor → X-Forwarded-For güvenilmez sayılır"
    )


def test_nginx_auth_uclarinda_limit_req():
    """İkinci savunma katmanı: uygulamaya hiç ulaşmadan sel saldırısını kes."""
    conf = (_ROOT / "deploy" / "nginx.conf.template").read_text(encoding="utf-8")
    assert "limit_req_zone" in conf and "limit_req zone=" in conf, (
        "nginx katmanında rate limit yok (yalnız uygulama katmanı)"
    )


def test_caddy_csp_ve_govde_siniri():
    """BUG #184: Caddy yolunda CSP ve gövde sınırı yoktu (nginx yolunda vardı)."""
    caddy = (_ROOT / "Caddyfile").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in caddy, "Caddyfile'da CSP yok"
    assert "max_size" in caddy, "Caddyfile'da istek gövdesi sınırı yok"
    # Yalnız YAPILANDIRMA satırları (yorumlar hariç) denetlenir
    kod = [l for l in caddy.splitlines() if not l.strip().startswith("#")]
    assert not any("0.0.0.0" in l for l in kod), (
        "Geçersiz site adresi (0.0.0.0) — Caddy IP için sertifika alamaz, TLS hatası verir"
    )


def test_env_ornekleri_kodla_ayni_degisken_adlarini_kullanir():
    """BUG #189: .env.prod.example OAuth adları KODLA uyuşmuyordu (OAUTH_ öneki yoktu).

    Operatör dokümandaki adı doldurur, kod başka adı okur → OAuth sessizce 501 döner.
    Bu kapı, env dokümanı ile kodun sözleşmesini bağlar.
    """
    from app.services.oauth import _PROVIDERS
    ornek = (_ROOT / ".env.prod.example").read_text(encoding="utf-8")
    eksik = []
    for provider, cfg in _PROVIDERS.items():
        for anahtar in (cfg["cid_env"], cfg["secret_env"]):
            if anahtar not in ornek:
                eksik.append(f"{provider}: {anahtar}")
    assert not eksik, (
        ".env.prod.example kodun beklediği değişken adlarını içermiyor:\n" + "\n".join(eksik)
    )


def test_deploy_surum_kimligini_enjekte_eder():
    """P9 (BUG #200): canlıda hangi kodun koştuğu ölçülebilmeli.

    `BUILD_COMMIT` enjekte edilmezse /api/health "bilinmiyor" döner ve deploy'un
    gerçekten güncellendiği (veya geri alma sonrası hangi sürüme dönüldüğü) DOĞRULANAMAZ.
    """
    compose = _compose_metni()
    assert "BUILD_COMMIT" in compose, "compose BUILD_COMMIT geçirmiyor"
    deploy = (_ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")
    assert "git rev-parse" in deploy, "deploy.sh git SHA'yı hesaplamıyor"


def test_kapasite_sinirlari_belgelenmis():
    """P5 (BUG #201): havuz PROCESS BAŞINA. Formül yazılı olmazsa worker artırınca
    'too many connections' ancak CANLIDA görülür."""
    runbook = (_ROOT / "docs" / "deployment" / "runbook.md").read_text(encoding="utf-8")
    assert "WEB_CONCURRENCY" in runbook and "max_connections" in runbook, (
        "Runbook kapasite formülünü belgelemiyor"
    )
    compose = _compose_metni()
    assert "DB_POOL_SIZE" in compose, "Havuz boyutu env ile ayarlanamıyor (küçük VM'de sorun)"
