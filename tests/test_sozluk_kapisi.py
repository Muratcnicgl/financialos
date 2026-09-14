"""
DOCS-015 (BUG #496): finansal sözlük koddan kopamaz.

Ölçüm (14 Eyl 2026): "reel bütçe, zikzak, emanet, görülen/tam net değer" gibi terimler kodda ve
arayüzde vardı, tanımlı tek yer yoktu (UX-034 mikro-kopya tutarsızlığının kaynağı). `docs/sozluk.md`
her terimi tanım + formül + KAYNAK ile yazar. Bu kapı:
  1. her `Kaynak:` satırındaki `dosya::sembol` çiftinin gerçekten var olduğunu (dosya var, sembol
     dosyada tanımlı) ölçer — sembol adı değişirse sözlük kırmızıya düşer,
  2. çekirdek terimlerin (reel bütçe, görülen/tam net değer, emanet, zikzak) sözlükte olduğunu,
  3. formül satırlarının kodla aynı işaret düzenini taşıdığını (görülen net değer) kilitler.
"""
from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
SOZLUK = KOK / "docs" / "sozluk.md"


def _kaynaklar():
    metin = SOZLUK.read_text(encoding="utf-8")
    ciftler = []
    for satir in metin.splitlines():
        if not satir.startswith("Kaynak:"):
            continue
        for m in re.finditer(r"`([\w./-]+\.(?:py|js|jsx))(?:::([\w.]+))?`", satir):
            ciftler.append((m.group(1), m.group(2)))
    return ciftler


def test_her_kaynak_dosya_ve_sembol_var():
    ciftler = _kaynaklar()
    assert len(ciftler) >= 25, f"kapsam tabanı: {len(ciftler)} kaynak"
    eksik = []
    for dosya, sembol in ciftler:
        yol = KOK / dosya
        if not yol.exists():
            eksik.append(f"{dosya} (dosya yok)")
            continue
        if sembol is None:
            continue
        kaynak = yol.read_text(encoding="utf-8")
        ad = sembol.split(".")[-1]           # `Account.is_emanet` → is_emanet
        desen = rf"^\s*(def|class|export (?:async )?function|export const|const)\s+{re.escape(ad)}\b|^\s*{re.escape(ad)}\s*[:=]"
        if not re.search(desen, kaynak, re.M):
            eksik.append(f"{dosya}::{sembol}")
    assert not eksik, f"sözlükteki kaynak koda uymuyor: {eksik}"


def test_cekirdek_terimler_var():
    metin = SOZLUK.read_text(encoding="utf-8")
    for baslik in ("## Reel bütçe", "## Görülen net değer", "## Tam net değer", "## Emanet", "## Zikzak", "## Günlük limit"):
        assert baslik in metin, f"sözlükte eksik: {baslik}"


def test_formul_kodla_ayni_isaret_duzeni():
    from decimal import Decimal

    from app.balance_rules import net_worth_full, net_worth_seen
    assert net_worth_seen(100, 50, 30, 20) == Decimal("100")       # nakit + yatırım − kart − kredi
    assert net_worth_full(100, 40, 10) == Decimal("130")           # + alacak − borç
    metin = SOZLUK.read_text(encoding="utf-8")
    assert "net_deger = nakit + yatırım − kart borcu − kredi borcu" in metin
    assert "net_deger_tam = net_deger + kişisel alacaklar − kişisel borçlar" in metin
