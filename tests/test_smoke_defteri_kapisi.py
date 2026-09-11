"""
BUG #388 KAPISI — SÜİT, ÇALIŞMA AĞACINDAKİ SMOKE DEFTERİNE YAZIYORDU.

Ölçülen (11 Eyl 2026): depo kökündeki smoke defteri **366 satır** "TESTTE AĞ ÇAĞRISI
ENGELLENDİ" taşıyordu — yani onu yazan canlı uygulama değil test süitiydi: lifespan
telafisi (`kacirilan_isleri_telafi_et`) haftalık smoke'u ağ kapalıyken koşturuyor,
`capture_smoke_failures` da varsayılan argümana **import anında bağlanmış** yola
yazıyordu. `*.log` ignore'da olduğu için `git status` hiç konuşmadı. BUG #289 (canlı DB)
ve #349 (canlı log) ile aynı sınıf: süit, ölçtüğü sistemin dosyalarına yazamaz.

Kilitlenen: yol ÇAĞRI ANINDA `SMOKE_KAYIT_DOSYASI`ndan çözülür; conftest onu test
dizinine çevirir; kök defter süit boyunca değişmez.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import app.services.smoke_tests as sm

KOK = Path(__file__).resolve().parent.parent
BASARISIZ = [{"api": "EVDS", "ok": False, "detail": "test"}]


def test_varsayilan_yol_CAGRI_ANINDA_env_den_cozulur(tmp_path, monkeypatch):
    hedef = tmp_path / "alt" / "defter.log"
    monkeypatch.setenv("SMOKE_KAYIT_DOSYASI", str(hedef))
    assert sm.capture_smoke_failures(BASARISIZ) == 1
    assert hedef.read_text(encoding="utf-8").startswith("SMOKE_FAIL|smoke|EVDS")


def test_suit_icinde_yol_calisma_agacinin_disinda_veya_test_dizininde():
    """conftest yönlendirmesi ölçülür: çözülen yol kök defter DEĞİL."""
    yol = sm.defter_yolu()
    assert yol != sm._LEDGER, "SMOKE_KAYIT_DOSYASI testte kurulmamış — süit gerçek deftere yazar"
    assert os.getenv("SMOKE_KAYIT_DOSYASI") == "logs/test/smoke-kayit.log"


def test_env_yoksa_uretim_varsayilani(monkeypatch):
    monkeypatch.delenv("SMOKE_KAYIT_DOSYASI", raising=False)
    assert sm.defter_yolu() == sm._LEDGER


@pytest.fixture
def kok_defter_boyutu():
    yol = KOK / sm._LEDGER
    return yol.stat().st_size if yol.exists() else 0


def test_basarisiz_smoke_kok_defteri_buyutmez(kok_defter_boyutu):
    """Uçtan uca: varsayılan argümanla çağrı — kök defter büyümez, test defteri büyür."""
    test_defteri = KOK / os.environ["SMOKE_KAYIT_DOSYASI"]
    once = test_defteri.stat().st_size if test_defteri.exists() else 0
    sm.capture_smoke_failures(BASARISIZ)
    yol = KOK / sm._LEDGER
    assert (yol.stat().st_size if yol.exists() else 0) == kok_defter_boyutu
    assert test_defteri.stat().st_size > once
