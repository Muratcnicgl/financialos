"""
DURUM ÖZETİ KAPISI (BUG #357 — 5 Eylül 2026).

NEDEN VAR
---------
`scripts/durum_ozeti.py` "neredeyiz" sorusunu bir metne değil ÖLÇÜME sorar; yeni bir oturum
oradan başlar. Ama bir durum aracının en tehlikeli arızası **sessizce eksik rapor
vermektir**: bir bölüm patlar, çıktı yine güzel görünür, okuyan eksik olduğunu anlamaz.

Bu kapı iki şeyi zorlar:

1. Betik **çıkış 0** ile bitmeli ve BEKLENEN BÖLÜMLERİN HEPSİNİ basmalı. Bir bölüm eklenip
   unutulursa ya da bir ayrıştırma kestirmesi bozulursa burada düşer.
2. Ölçülemeyen bir bölüm **"ÖLÇÜLEMEDİ" diye YAZILMALI**, sessizce atlanmamalı — bilinmeyen
   sıfır değildir (L45). `_guvenli()` bunu garanti eder ve testi bu davranışın üstünde durur.

MUTASYON 2/2 — bir bolumu ciktidan cikar -> kapi kirmizi ·
_guvenli()'yi sessiz atlamaya cevir -> "OLCULEMEDI" testi kirmizi
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
BETIK = KOK / "scripts" / "durum_ozeti.py"

#: Çıktıda bulunması ZORUNLU bölümler. Yeni bölüm eklenirse buraya da yazılır —
#: yoksa "eklendi ama basılmıyor" hâli sessiz kalır.
BOLUMLER = ("yerel HEAD", "canlı damga", "çalışma ağacı",
            "backlog", "bayat belge", "erişilebilirlik")


def _kosur(*ek: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(BETIK), *ek],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(KOK), timeout=300,
        env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )


def test_BETIK_kosuyor_ve_TUM_bolumleri_basiyor():
    sonuc = _kosur("--hizli")
    assert "Traceback" not in (sonuc.stderr or ""), (
        f"durum_ozeti.py çöktü:\n{sonuc.stderr}"
    )
    assert sonuc.returncode == 0, f"çıkış {sonuc.returncode}\n{sonuc.stdout}{sonuc.stderr}"
    eksik = [b for b in BOLUMLER if b not in sonuc.stdout]
    assert not eksik, (
        f"Bu bölümler çıktıda yok: {eksik}\nBir durum aracının en tehlikeli arızası, "
        f"sessizce eksik rapor vermektir.\n---\n{sonuc.stdout}"
    )


def test_OLCULEMEYEN_bolum_SESSIZ_atlanmaz():
    """`_guvenli` bir hatayı yutup boş bırakmaz; 'ÖLÇÜLEMEDİ' yazar."""
    sys.path.insert(0, str(KOK))
    from scripts.durum_ozeti import _guvenli

    def patlar():
        raise RuntimeError("deney")

    sonuc = _guvenli(patlar)
    assert "ÖLÇÜLEMEDİ" in sonuc, f"hata sessizce yutuldu: {sonuc!r}"
    assert _guvenli(lambda: None) == "ÖLÇÜLEMEDİ", "boş sonuç da ölçülememiş sayılmalı"
