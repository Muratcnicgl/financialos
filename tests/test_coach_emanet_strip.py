"""
W3-030 (CO-001): EMANET KASA halüsinasyon filtresi format-bağımsız olmalı.

Kök sorun: `_EMANET_HEADER_RE` yalnız köşeli-parantez `[5. EMANET KASA]` yakalıyordu.
Ama V3 prompt kural 13 markdown başlık (`## 5. Emanet Kasa`) istiyor → emanet 0/yok
iken bu bölüm sızıyordu (ADR-001: koç prompt'a değil, kod filtresine güvenmeli).

Filtre cockpit'te emanet_kasa == 0 iken bölümü BAŞLIK FORMATINDAN BAĞIMSIZ silmeli;
sonraki bölümleri yememeli; emanet > 0 iken bölüme dokunmamalı.
"""
from __future__ import annotations

from app.coach import _postprocess_report


def _report(emanet_header: str) -> str:
    return (
        "## 4. Yatırım\n"
        "TLY fonu güçlü.\n\n"
        f"{emanet_header}\n"
        "Emanet varlık bulunmamaktadır.\n\n"
        "## 6. Sonuç\n"
        "Nakit akışına odaklan."
    )


def test_markdown_emanet_basligi_silinir_emanet_sifir():
    text = _report("## 5. Emanet Kasa")
    out = _postprocess_report(text, {"emanet_kasa": 0})
    assert "Emanet varlık bulunmamaktadır" not in out
    assert "5. Emanet Kasa" not in out
    # Sonraki bölüm KORUNMALI (over-consume yok)
    assert "## 6. Sonuç" in out
    assert "Nakit akışına odaklan" in out
    # Önceki bölüm korunmalı
    assert "## 4. Yatırım" in out


def test_h3_ve_bold_varyant_silinir():
    for header in ("### 5. EMANET KASA", "**5. Emanet Kasa**", "5. EMANET KASA"):
        out = _postprocess_report(_report(header), {"emanet_kasa": 0})
        assert "Emanet varlık bulunmamaktadır" not in out, header
        assert "## 6. Sonuç" in out, header


def test_koseli_parantez_regresyon():
    # Eski format da hâlâ çalışmalı
    text = (
        "[4. YATIRIM]\nTLY.\n\n"
        "[5. EMANET KASA]\nEmanet yok.\n\n"
        "[6. SONUÇ]\nDevam."
    )
    out = _postprocess_report(text, {"emanet_kasa": 0})
    assert "Emanet yok" not in out
    assert "[6. SONUÇ]" in out


def test_emanet_pozitifse_bolum_korunur():
    text = _report("## 5. Emanet Kasa")
    out = _postprocess_report(text, {"emanet_kasa": 15000})
    assert "5. Emanet Kasa" in out
    assert "Emanet varlık bulunmamaktadır" in out
