"""
BUG #249 (denetim D40) — RUNBOOK'TAKİ OPERASYON KOMUTLARI KONTEYNER DIŞINDA KOŞUYORDU.

Runbook `python -m scripts.beta_invite --email ...` diyordu. Host kabuğunda `DATABASE_URL`
tanımlı DEĞİLDİR (o değişken `.env.prod` ile konteynere verilir) → komut **yerel SQLite
dosyasına** yazar, "davet üretildi" der, davetli canlıda 403 alır. Kapalı beta fail-closed
olduğu için bu sırada kimse kayıt olamaz: beta açılışı durur ve operatör nedenini göremez.

Aynı repoda doğru form zaten vardı (`README.md`): `docker compose ... exec -T backend`.
Yani belge kendi içinde tutarsızdı — bu kapı iki yüzeyi eşitler.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
RUNBOOK = KOK / "docs" / "deployment" / "runbook.md"

# Prod veritabanına dokunan operasyon script'leri (host kabuğunda anlamsız/zararlı).
_DB_SCRIPTLERI = ("beta_invite", "beta_triage", "beta_metrics", "backup", "restore")


def _kod_satirlari() -> list[str]:
    metin = RUNBOOK.read_text(encoding="utf-8")
    return [s.strip() for s in metin.splitlines()
            if s.strip().startswith(("python -m scripts", "docker compose", "$COMPOSE"))]


def test_kapsam_tabani_runbook_komutlari_bulunuyor():
    """L23: tarama boş dönerse kapı sessizce yeşil kalır."""
    satirlar = _kod_satirlari()
    assert len(satirlar) >= 5, f"Runbook'ta yalnız {len(satirlar)} komut bulundu — tarama bozuk"


@pytest.mark.parametrize("script", _DB_SCRIPTLERI)
def test_db_ye_dokunan_komutlar_konteyner_icinde_kosar(script):
    kacaklar = [s for s in _kod_satirlari()
                if f"scripts.{script}" in s and "exec" not in s]
    assert not kacaklar, (
        f"Bu komutlar host kabuğunda koşuyor (prod DB'yi GÖRMEZ, sessizce yerel SQLite'a "
        f"yazar): {kacaklar}"
    )


def test_runbook_konteyner_uyarisini_tasiyor():
    metin = RUNBOOK.read_text(encoding="utf-8")
    assert re.search(r"konteyner\s+İÇİNDE", metin), (
        "Runbook, komutların konteyner içinde koştuğunu açıkça söylemiyor — operatör "
        "kopyalayıp host'ta koşturur"
    )
