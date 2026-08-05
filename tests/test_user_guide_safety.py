"""
P9 (Wave-9) — BUG #207: kullanıcı rehberi BAYAT ve TEHLİKELİ yönlendirme içeriyordu.

`docs/user-guide/README.md` Wave-9 öncesinden kalmıştı ve "demo veri" için
`scripts/setup_data` öneriyordu. O script `drop_all` yapar: rehberi izleyen bir
kullanıcı **kendi tüm verisini siler** ve yerine başkasının kanonik verisi yüklenir.
Ayrıca Wave-9'da eklenen ürünleşme özellikleri (davet kodu, uygulanan kurallar, güvenli
demo veri, hesabı sil/dışa aktar, saat dilimi) rehberde hiç geçmiyordu.

Bu kapı, kullanıcıya dönük dokümanın yıkıcı geliştirici araçlarını ÖNERMEDİĞİNİ ve
mevcut özellikleri kapsadığını kilitler.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_REHBER = _ROOT / "docs" / "user-guide" / "README.md"

# Kullanıcıya ASLA önerilmemesi gereken yıkıcı geliştirici araçları
YIKICI_ARACLAR = ["scripts/setup_data", "scripts.setup_data",
                  "cleanup_orphan_traces", "drop_all"]


def _kullaniciya_onerilen_satirlar() -> list[str]:
    """Uyarı bağlamı olmayan satırlar (uyarı satırında araç adı geçebilir)."""
    satirlar = []
    for line in _REHBER.read_text(encoding="utf-8").splitlines():
        alt = line.lower()
        # Uyarı bağlamı: açık "kullanma" uyarısı VEYA blockquote (>) ile verilen
        # sürüm notu. Bunlarda araç adının geçmesi zorunlu (neden yasak olduğunu anlatır).
        if (line.lstrip().startswith(">") or "kullanma" in alt or "⚠️" in line
                or "siler" in alt or "sıfırlar" in alt):
            continue
        satirlar.append(line)
    return satirlar


@pytest.mark.parametrize("arac", YIKICI_ARACLAR)
def test_rehber_yikici_araci_onermez(arac):
    ihlal = [l for l in _kullaniciya_onerilen_satirlar() if arac in l]
    assert not ihlal, (
        f"Kullanıcı rehberi yıkıcı aracı ({arac}) uyarısız öneriyor:\n" + "\n".join(ihlal)
    )


def test_rehber_guvenli_demo_yolunu_anlatir():
    icerik = _REHBER.read_text(encoding="utf-8").lower()
    assert "örnek veriyle gez" in icerik or "onboarding/demo" in icerik, (
        "Rehber güvenli demo veri yolunu anlatmıyor (kullanıcı yıkıcı script arar)"
    )


@pytest.mark.parametrize("konu", [
    "davet kodu",        # P7: kapalı beta kaydı
    "hesabını sil",      # KVKK
    "saat dilimi",       # H4
    "tavsiyesi vermez",  # P4: yatırım tavsiyesi değildir
    "engellenir",        # H3: uygulanan kurallar
])
def test_rehber_wave9_ozelliklerini_kapsar(konu):
    icerik = _REHBER.read_text(encoding="utf-8").lower()
    assert konu in icerik, f"Rehberde '{konu}' anlatılmıyor (özellik var ama kullanıcı bilmiyor)"


def test_rehber_bilinen_sinirlari_soyler():
    """Beta kullanıcısı neyin eksik olduğunu bilmeli (güven = dürüstlük)."""
    icerik = _REHBER.read_text(encoding="utf-8").lower()
    assert "bilinen sınırlar" in icerik
    assert "banka bağlantısı" in icerik
