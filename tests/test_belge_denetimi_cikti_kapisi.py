"""
BELGE DENETİMİ — ÇIKTI YOLU KAPISI (BUG #363).

NEDEN VAR: bir kapının hata yolu, başarı yolundan daha dayanıklı olmalıdır. Çünkü hata
yolu ancak söyleyecek sözü olduğunda koşar; orada çökerse kapı **tam da işe yarayacağı
anda** susar.

ÖLÇÜLEN DEFEKT (9 Eyl 2026): `belge_denetimi.py` bulduğu ölü yönlendirmenin kaynak
satırını olduğu gibi basıyor. O satır TARANAN BELGENİN içeriği — karakter kümesini biz
seçmiyoruz. Fix defterine içinde `✅` geçen bir satır eklendiğinde kapı, ilk bulguyu
yazarken `UnicodeEncodeError` ile öldü (Windows Türkçe konsol = cp1254) ve geri kalan
bulguları hiç söylemedi.

Aynı sınıf bu dosyada BİR KEZ daha yakalanmıştı: `→` işareti cp1254'te yok diye bizim
biçim dizemiz ASCII oka çevrilmişti. Ama düzeltme yalnız BİZİM yazdığımız yarıya
uygulanmış, bir satır sonra basılan BELGE İÇERİĞİ açıkta kalmıştı (L84 — bir düzeltmeyi
ikiye bölmek, hiç yapmamaktan yanıltıcıdır).

KİLİTLENEN DEĞİŞMEZ: konsol kodlaması kısıtlıyken (cp1254) modül içe aktarılıp
kodlanamayan bir karakter basıldığında süreç çökmez. Mutasyon (9 Eyl 2026): modüldeki
`sys.stdout.reconfigure(errors="replace")` satırı kaldırıldığında bu test KIRMIZI döner.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _kos(betik: str) -> subprocess.CompletedProcess:
    """Kısıtlı kod sayfasıyla ayrı süreçte koşar (stdout boru → PYTHONIOENCODING geçerli)."""
    return subprocess.run(
        [sys.executable, "-c", betik],
        cwd=str(KOK),
        env=dict(os.environ, PYTHONIOENCODING="cp1254"),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_kodlanamayan_karakter_kapiyi_coketmez():
    """Bulgu satırında `✅` varsa kapı, bulguyu yazarken ölmemeli."""
    sonuc = _kos(
        "import scripts.belge_denetimi\n"
        "print('bulgu satiri: \\u2705 kapali madde')\n"
        "print('ikinci bulgu da yazilabilmeli')\n"
    )
    assert "Traceback" not in sonuc.stderr, (
        "kapı, bulgu satırını yazarken çöktü — söyleyecek sözü olduğu anda susuyor:\n"
        + sonuc.stderr[-800:]
    )
    assert sonuc.returncode == 0, f"beklenmedik çıkış kodu {sonuc.returncode}"
    # Kaybolan değil, DEĞİŞTİRİLEN karakter: ikinci satır da basılmış olmalı.
    assert "ikinci bulgu da yazilabilmeli" in sonuc.stdout


def test_kapinin_kendi_kosumu_kisitli_konsolda_da_tamamlanir():
    """Kapı uçtan uca koşar; çıkış kodu bulguya ait olur, çökmeye değil.

    Sözleşme: 0 (temiz) ya da 1 (ölü yönlendirme var) — ikisi de KARARDIR. Traceback ise
    karar değildir ve `| tail` gibi bir boruya girdiğinde 0 gibi okunur (L68/L85).
    """
    sonuc = subprocess.run(
        [sys.executable, "scripts/belge_denetimi.py"],
        cwd=str(KOK),
        env=dict(os.environ, PYTHONIOENCODING="cp1254"),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert "Traceback" not in sonuc.stderr, sonuc.stderr[-800:]
    assert sonuc.returncode in (0, 1), f"beklenmedik çıkış kodu {sonuc.returncode}"
    assert "[KAPI] " in sonuc.stdout
