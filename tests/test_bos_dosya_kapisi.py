"""
FE-025 (BUG #484): 0 baytlık kaynak dosyası depoda yaşamaz.

Ölçüm (14 Eyl 2026): `frontend/src/components/{Header,Loading,QuickEntry,TabBar}.jsx` ilk
commit'ten beri 0 bayttı ve hiçbir yerden import edilmiyordu (grep: 0 atıf). Boş dosya, "bir
gün doldurulur" vaadiyle duran ölü koddur; IDE'de yanıltır, ölü kod kapısına görünmez.
"""
from __future__ import annotations

from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
TARANAN = ("frontend/src", "app", "scripts", "tests")
UZANTI = {".js", ".jsx", ".py", ".css"}


def test_sifir_bayt_kaynak_dosyasi_yok():
    bos = [
        str(p.relative_to(KOK))
        for kok in TARANAN
        for p in (KOK / kok).rglob("*")
        if p.is_file() and p.suffix in UZANTI and "node_modules" not in p.parts
        and p.name != "__init__.py" and p.stat().st_size == 0
    ]
    assert not bos, f"0 baytlık kaynak dosyası: {bos}"
