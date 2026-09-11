"""
PERF-010 / BUG #418 KAPISI — SIK FİLTRELENEN FK SÜTUNLARI İNDEKSLİ.

Ölçülen (12 Eyl 2026): 16 FK sütunu tekil indekssizdi; yedisi her istekte filtre/join
kolonu (beş `user_id`, `recurring_expenses.account_id`, `audit_log.workspace_id`). Bugünkü
ölçekte hız farkı ölçülemez — hijyen/büyüme önlemi, maliyeti sıfıra yakın.

Kilitlenen: her `user_id` FK sütunu indeksli (model VE göç aynı adla); indekssiz FK sayısı
ratchet (≤ 9); göç dosyasındaki indeks adları modeldeki adlarla birebir.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from app.models import Base

KOK = Path(__file__).resolve().parent.parent


def _indekssiz_fk():
    out = []
    for t in Base.metadata.sorted_tables:
        tekil = {list(ix.columns)[0].name for ix in t.indexes} | {c.name for c in t.primary_key.columns}
        for c in t.columns:
            if c.foreign_keys and c.name not in tekil and not c.unique:
                out.append(f"{t.name}.{c.name}")
    return out


def test_her_user_id_fk_indeksli():
    eksik = [x for x in _indekssiz_fk() if x.endswith(".user_id")]
    assert eksik == [], f"user_id FK indekssiz: {eksik}"


def test_indekssiz_fk_sayisi_buyumuyor():
    kalan = _indekssiz_fk()
    assert len(kalan) <= 9, f"indekssiz FK arttı ({len(kalan)}): {kalan}"
    assert len(kalan) >= 5, "sayı düştüyse tavanı da düşür (kazanım kilidi)"


def test_goc_ile_model_ayni_indeks_adlarini_kullanir():
    yol = KOK / "alembic" / "versions" / "f7a8b9c0d1e2_fk_indeksleri.py"
    spec = importlib.util.spec_from_file_location("goc_fk", yol)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    for ad, tablo, kolon in mod.INDEKSLER:
        adlar = {ix.name: [c.name for c in ix.columns] for ix in Base.metadata.tables[tablo].indexes}
        assert adlar.get(ad) == [kolon], f"{tablo}: göç {ad} → model {adlar.get(ad)}"
