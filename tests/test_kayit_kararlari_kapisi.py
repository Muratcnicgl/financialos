"""
KAYIT KARARLARI KAPISI (7 Agu 2026) — master durum raporunun YANILGI-1/2/3/4/5/7'si.

NEDEN BU KAPI VAR
-----------------
6 Agu 2026'da uretilen master durum raporu, diskin kendi anlatisiyla celistigi yedi nokta
buldu. Bunlarin dordu "bayat sayi" (kolay), ucu ise **yazili olmayan karar**:

  * milestone/tag disiplini 18 Tem'de birakildi ama hicbir yerde yazmiyordu → bir sonraki
    oturum bunu sessiz curume sanardi (YANILGI-7),
  * MCP memory 19 gundur donmustu ve hala "tek gercek kaynak" gibi aniliyordu (YANILGI-1),
  * bug envanteri uc ayri yere dagilmisti, hangisinin resmi oldugu belirsizdi (YANILGI-5).

Kararlari dosyaya yazmak yetmez: **belge iddiasi kanit degildir (L17).** Yazilan cumle
silinirse ya da sessizce eskirse bunu olcen bir sey olmali — bu kapi odur.

KAPSAM TABANI (L11 / H25): kapi kac dosyayi denetledigini assert eder; taranan dosya sayisi
tabanin altina duserse kapi kendini KIRMIZI yapar (kapsamsiz kapi = olu kapi).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent

# (dosya, aranan_isaret, aciklama) — isaretler KARAR cumlelerinin degismez cekirdegidir.
BEKLENEN: list[tuple[str, str, str]] = [
    ("PROJE.md", "AKTİF HAT: PUBLISH YOLU",
     "YANILGI-2: aktif hat Wave-8 degil publish yolu"),
    ("PROJE.md", "Milestone/tag disiplini 18 Tem 2026'da BIRAKILDI",
     "YANILGI-7: metodoloji degisimi yazili olmali"),
    ("PROJE.md", "MCP MEMORY STATÜSÜ",
     "YANILGI-1: MCP tek gercek kaynak degil, tarihsel arsiv"),
    ("PROJE.md", "master-durum-raporu-2026-08-06.md",
     "devir belgesine isaretci"),
    ("docs/kalite-seruveni/masterprompt-publish.md", "MİLESTONE/TAG DİSİPLİNİ BIRAKILDI",
     "YANILGI-7 masterprompt tarafi"),
    ("docs/kalite-seruveni/masterprompt-publish.md", "MCP MEMORY = TARİHSEL ARŞİV",
     "YANILGI-1 masterprompt tarafi"),
    ("docs/kalite-seruveni/masterprompt-publish.md", "TEK BUG ENVANTERİ",
     "YANILGI-5 masterprompt tarafi"),
    ("docs/kalite-seruveni/uygulanan-fixler.md", "TEK RESMÎ BUG ENVANTERİDİR",
     "YANILGI-5: envanterin kendisi kendini ilan eder"),
    ("docs/kalite-seruveni/backlog.md", "**521**",
     "YANILGI-4: backlog toplami 520 degil 521"),
]

TARANAN_DOSYALAR = sorted({d for d, _, _ in BEKLENEN})
TABAN_DOSYA = 4      # bu kapinin dokunmasi gereken en az dosya sayisi
TABAN_ISARET = 9     # en az bu kadar karar-isareti denetlenmeli


def _oku(rel: str) -> str:
    yol = KOK / rel
    assert yol.exists(), f"kapi olcemiyor: {rel} yok"
    return yol.read_text(encoding="utf-8")


@pytest.mark.parametrize("rel,isaret,neden", BEKLENEN,
                         ids=[f"{d}:{n}" for d, _, n in BEKLENEN])
def test_karar_cumlesi_diskte_duruyor(rel: str, isaret: str, neden: str) -> None:
    """Her karar cumlesi ilgili dosyada YAZILI olmali (silinirse kapi kirmizi)."""
    metin = _oku(rel)
    assert isaret in metin, f"{rel} icinde karar isareti kayboldu ({neden}): {isaret!r}"


def test_kapinin_kendi_kapsami_olculur() -> None:
    """L11/H25: kapi kac dosya + kac isaret denetledigini assert eder."""
    assert len(TARANAN_DOSYALAR) >= TABAN_DOSYA, (
        f"kapsam coktu: yalniz {len(TARANAN_DOSYALAR)} dosya denetleniyor "
        f"(taban {TABAN_DOSYA}) — kapi olcmuyor olabilir"
    )
    assert len(BEKLENEN) >= TABAN_ISARET, (
        f"karar-isareti sayisi {len(BEKLENEN)} < taban {TABAN_ISARET}"
    )


def test_eski_bayat_iddialar_geri_gelmedi() -> None:
    """Duzeltilen bayat sayilar/ifadeler geri sizarsa kirmizi."""
    claude = _oku("PROJE.md")
    assert "TOTAL coverage %92" not in claude, "coverage iddiasi %92'ye geri dondu (olculen: %93)"
    assert not re.search(r"\*\*Aktif goal:\*\*\s*🟡\s*\*\*WAVE-8[^\n]*DEVAM", claude), \
        "PROJE.md yeniden 'aktif goal WAVE-8 DEVAM' diyor (publish hatti aktif)"

    backlog = _oku("docs/kalite-seruveni/backlog.md")
    assert "| **TOPLAM** | **18 kategori** | **520** |" not in backlog, \
        "backlog toplami yeniden 520 (gercek: 521)"


def test_devir_belgesi_diskte_ve_dolu() -> None:
    """Master durum raporu var, bos degil ve isaretcisi dogru dosyayi gosteriyor."""
    rapor = KOK / "docs" / "kalite-seruveni" / "master-durum-raporu-2026-08-06.md"
    assert rapor.exists(), "devir belgesi (master durum raporu) diskte yok"
    bayt = rapor.stat().st_size
    assert bayt > 1_000_000, f"devir belgesi beklenenden kucuk ({bayt} bayt) — icerik kaybolmus olabilir"
    ilk = rapor.read_text(encoding="utf-8", errors="replace")[:400]
    assert "MASTER DURUM RAPORU" in ilk, "devir belgesinin basligi degismis"


def test_mcp_ledger_esigi_gercekten_olculuyor() -> None:
    """
    BUG #255: `scripts/mcp_sync_report.py` HER durumda 0 donuyordu — birikme sessizdi.
    Bu test davranisi olcer: esigin altinda 0, ustunde 2.
    """
    sys.path.insert(0, str(KOK))
    from scripts import mcp_sync_report as msr

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sahte = Path(td) / "ledger.log"
        eski = msr.LEDGER
        try:
            msr.LEDGER = sahte

            sahte.write_text("", encoding="utf-8")
            assert msr.main([]) == 0, "bos ledger yesil olmali"

            az = "\n".join(f"abc{i:04d}|2026-08-07T00:00:00+03:00|deneme" for i in range(3))
            sahte.write_text(az + "\n", encoding="utf-8")
            assert msr.main([]) == 0, "esigin altindaki birikme yesil olmali"

            cok = "\n".join(f"abc{i:04d}|2026-08-07T00:00:00+03:00|deneme"
                            for i in range(msr.ESIK + 5))
            sahte.write_text(cok + "\n", encoding="utf-8")
            assert msr.main([]) == 2, "esik asildiginda cikis kodu 2 olmali (sessiz buyume yasak)"
        finally:
            msr.LEDGER = eski
