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


def test_mcp_defteri_KAPALI_kalir() -> None:
    """
    MCP SYNC DEFTERI 4 EYLUL 2026'DA KAPATILDI (Wave-Y / Y5) — bu test o karari korur.

    ONCEKI HALI (tarihsel): burada `scripts/mcp_sync_report.py`'nin esik davranisi
    olculuyordu (BUG #255: her durumda 0 donuyordu, birikme sessizdi). O kapinin KONUSU
    artik yok:

      * 7 Agu 2026 — flush 19 gundur hic kosulmamis, defterde 186 satir birikmisti;
        ayni gun MCP resmen TARIHSEL ARSIV ilan edildi.
      * 4 Eyl 2026 — defter 300 satira cikmisti, flush hala hic kosulmamisti.

    Yani `post-commit` yakalamasi **hic kosulmayacak bir flush icin** calisiyordu. Boyle
    bir defter zararsiz degildir: her bakan "300 satir bekleyen is var" sanir.
    **SAHTE YUKUMLULUK, BORCTAN DAHA KOTUDUR — cunku odenmez ve unutulmaz.**

    Bir kapiyi konusu bittigi icin silmek dogru; ama karari korumasiz birakmak degil.
    Bu test o yuzden yerine gecti: yakalama sessizce geri acilirsa burada dusar. Bilincli
    olarak geri acilacaksa bu testin GEREKCESIYLE guncellenmesi gerekir.
    """
    assert not (KOK / "scripts" / "mcp_sync_report.py").exists(), (
        "scripts/mcp_sync_report.py geri gelmis — MCP defteri kapatilmisti (Wave-Y/Y5). "
        "Bilincli bir karar ise bu testi gerekcesiyle guncelle."
    )
    hook = (KOK / ".githooks" / "post-commit").read_text(encoding="utf-8")
    assert ".mcp-sync-pending.log" not in hook or "printf" not in hook, (
        ".githooks/post-commit yeniden defter YAKALIYOR — kapatilmis bir defteri doldurmak, "
        "kimsenin okumayacagi bir borc uretir (Wave-Y/Y5 karari)."
    )
