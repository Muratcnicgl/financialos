"""
BUG #343 KAPISI — RAPOR, GERÇEK ÖLÇÜMÜ "ÖLÇÜM YOK" SANIYORDU (sessizce).

ÖLÇÜLEN OLAY (4 Eylül 2026, Wave-Y/Y2)
--------------------------------------
`saglik.ps1` erişilebilirlik kaydını yazdı ve dosya diskte DURUYORDU:

    ﻿zaman_utc,saglikli
    2026-09-04T11:13:47Z,1

Rapor yine de **"OLCUM YOK — bu donemde hic kayit yok"** dedi. Sebep: PowerShell'in
`Add-Content -Encoding UTF8`'i dosya başına **BOM** koyuyor; düz `utf-8` ile okunduğunda
ilk sütun adı `\\ufeffzaman_utc` oluyor, `zaman_utc` anahtarı bulunamıyor ve her satır
sessizce eleniyordu.

**Bu, projenin avladığı sınıfın ta kendisi:** bir okuyucu, var olan ölçümü yokluk sanıyor.
Ve tam da Y2'nin kapatmak için var olduğu körlüğü üretiyor — "veri yok" cümlesi, "sistem
sağlıklı" ile karıştırılabilecek en tehlikeli çıktıdır.
(Aynı BOM tuzağının PowerShell tarafı: `tests/test_ps1_bom_kapisi.py`. Aynı bayt, iki
yönde iki ayrı arıza: orada eksikliği, burada varlığı kırıyor.)

KİLİTLENEN İKİNCİ SÖZLEŞME: KAYIP SLOT KESİNTİDİR
--------------------------------------------------
Sağlık görevi 10 dakikada bir koşar. Makine kapalıyken satır YAZILMAZ. Yalnız yazılmış
satırlara bakan bir rapor, makinenin kapalı olduğu geceyi **%100 sağlıklı** gösterirdi —
ölçmediğini mükemmel sanmak (L45). Payda bu yüzden **beklenen slot**tur.
"""
from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

import pytest

import scripts.erisilebilirlik_raporu as rapor


@pytest.fixture
def kayit(tmp_path, monkeypatch):
    """Raporu geçici bir kayıt dosyasına bağlar (canlı `logs/` dosyasına dokunmaz)."""
    yol = tmp_path / "erisilebilirlik.csv"
    monkeypatch.setattr(rapor, "KAYIT", yol)
    return yol


def _yaz(yol, satirlar: list[tuple[datetime, int]], bom: bool):
    metin = "zaman_utc,saglikli\n" + "".join(
        f"{t.strftime('%Y-%m-%dT%H:%M:%SZ')},{ok}\n" for t, ok in satirlar)
    yol.write_bytes((("﻿" if bom else "") + metin).encode("utf-8"))


def test_BOM_LU_kayit_OKUNUR(kayit):
    """
    PowerShell'in yazdığı gerçek biçim budur. Okunamazsa rapor sessizce "ölçüm yok" der
    ve izleme, izlenmiyormuş gibi görünür — Y2'nin varlık sebebi ölür.
    """
    simdi = datetime.now(timezone.utc)
    _yaz(kayit, [(simdi - timedelta(minutes=10), 1), (simdi, 1)], bom=True)
    assert len(rapor._oku(7)) == 2, "BOM'lu kayıt okunamadı — rapor körleşir"


def test_BOMSUZ_kayit_da_OKUNUR(kayit):
    """Elle düzenlenmiş / başka araçla yazılmış dosya da okunmalı (dar çözüm olmasın)."""
    simdi = datetime.now(timezone.utc)
    _yaz(kayit, [(simdi, 1)], bom=False)
    assert len(rapor._oku(7)) == 1


def test_KAYIT_YOKKEN_yuzde_BASILMAZ(kayit, capsys):
    """
    L45: sıfır gözlem %100 değildir. Boş dönemde yüzde basmak, izlemenin ölü olduğu günü
    "mükemmel gün" diye raporlamak olurdu.
    """
    assert rapor.main(["--gun", "7"]) == 2
    cikti = capsys.readouterr().out
    assert "OLCUM YOK" in cikti
    # Ölçüt "%100 geçmesin" DEĞİL — çıktı zaten *"Bu %100 DEGILDIR"* diye uyarıyor ve
    # ilk yazımda kendi uyarısına takıldı. Asıl sözleşme: HİÇBİR erişilebilirlik ORANI
    # basılmaması. (Bir ölçütü, ölçtüğü şeyin niyetine göre daraltmak gerekir.)
    assert "ERISILEBILIRLIK:" not in cikti, cikti


def test_KAYIP_SLOT_KESINTI_SAYILIR(kayit, capsys):
    """
    Payda beklenen slottur. 60 dakikalık pencerede 6 slot beklenir; yalnız 2 kayıt varsa
    erişilebilirlik %100 DEĞİL, ~%33'tür — kullanıcının gördüğü de budur.
    """
    simdi = datetime.now(timezone.utc)
    _yaz(kayit, [(simdi - timedelta(minutes=60), 1), (simdi, 1)], bom=True)
    assert rapor.main(["--gun", "7"]) == 0
    cikti = capsys.readouterr().out
    assert "%100.00" not in cikti, cikti
    assert "kayip slot" in cikti, cikti


def test_SAGLIKSIZ_kayit_yuzdeyi_DUSURUR(kayit, capsys):
    """`saglikli=0` satırı da kesintidir — yalnız kayıp slotlar değil."""
    simdi = datetime.now(timezone.utc)
    _yaz(kayit, [(simdi - timedelta(minutes=10), 1), (simdi, 0)], bom=True)
    rapor.main(["--gun", "7"])
    cikti = capsys.readouterr().out
    assert "basarisiz 1" in cikti, cikti
    assert "saglik BASARISIZ" in cikti, cikti


def test_MODUL_ADI_deftere_yazildigi_gibi():
    """Belge komutu ile modül adı ayrışmasın (BUG #310 sınıfı)."""
    assert importlib.import_module("scripts.erisilebilirlik_raporu") is rapor
