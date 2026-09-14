"""
DOCS-012 / BUG #473 KAPISI — VERİ MODELİ BELGESİ METADATA İLE AYNI.

Elle yazılan ER belgesi ilk göçte bayatlar; `docs/architecture/data-model.md` üretilir ve bu
kapı üreticiyi çağırıp diskteki metinle karşılaştırır (backlog indeksiyle aynı desen). Kapsam
tabanı: en az 25 tablo, para sütunları işaretli, denetlenen/saklama rozetleri gerçek kaynaktan.
"""
from __future__ import annotations

from scripts.veri_modeli_belgesi import HEDEF, uret


def test_belge_guncel():
    assert HEDEF.exists(), "docs/architecture/data-model.md yok — üret: python scripts/veri_modeli_belgesi.py --yaz"
    assert HEDEF.read_text(encoding="utf-8") == uret(), (
        "Veri modeli belgesi modelden geride. Güncelle: python scripts/veri_modeli_belgesi.py --yaz")


def test_belge_kapsam_ve_rozetler():
    m = uret()
    assert m.count("\n## `") >= 25, "kapsam tabanı (L45)"
    assert "## `audit_log` — saklama 365 gün" in m
    assert "## `accounts` — denetlenir" in m
    assert "| `balance` | NUMERIC(19, 4) | hayır | 0.0 |  | para |" in m
    assert "FLOAT | evet |  |  | para" not in m, "oran/faiz sütunu para diye işaretlenmiş"
