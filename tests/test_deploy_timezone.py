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
