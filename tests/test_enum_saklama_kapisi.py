"""
DATA-017 / BUG #420 KAPISI — SQLEnum SAKLAMA BİÇİMİ BELİRSİZLİK TAŞIMAZ.

Ölçülen (12 Eyl 2026): 11 SQLEnum sütunu. `values_callable` yalnız 3'ünde; madde bunu
"tutarsız" sayıyordu. Ama saklanan ad ile değer arasındaki fark yalnız adı ≠ değeri olan
enum'larda anlam taşır: o ikisi (PriceSource, OperationName) zaten `values_callable`
taşıyor; kalan 8'in her üyesinde ad == değer — SQLAlchemy'nin hangisini yazdığı fark
etmez. Hepsine `values_callable` eklemek davranış değiştirmeden dosya karıştırmak olurdu;
asıl risk bir gün ad ≠ değer olan yeni bir üye eklenmesidir.

Kilitlenen: her SQLEnum sütunu ya `values_callable` taşır ya da enum'unun tüm üyeleri
ad == değer. Aksi → kırmızı (saklanan metin belirsizleşir, PG enum tipi kırılır).
"""
from __future__ import annotations

from sqlalchemy import Enum as SQLEnum

from app.models import Base


def _enum_sutunlari():
    for t in Base.metadata.sorted_tables:
        for c in t.columns:
            if isinstance(c.type, SQLEnum) and c.type.enum_class is not None:
                yield t.name, c.name, c.type


def test_her_sqlenum_saklamasi_belirsizlik_tasimaz():
    sutunlar = list(_enum_sutunlari())
    assert len(sutunlar) >= 8, f"yalnız {len(sutunlar)} SQLEnum — tarayıcı bozuk olabilir (L45)"
    ihlal = []
    for tablo, kolon, tip in sutunlar:
        farkli = [m.name for m in tip.enum_class if m.name != m.value]
        if farkli and not tip.values_callable:
            ihlal.append(f"{tablo}.{kolon} ({tip.enum_class.__name__}): ad≠değer {farkli} ama values_callable yok")
    assert ihlal == [], "\n".join(ihlal)


def test_values_callable_olanlar_degeri_yazar():
    for tablo, kolon, tip in _enum_sutunlari():
        if tip.values_callable:
            assert set(tip.values_callable(tip.enum_class)) == {m.value for m in tip.enum_class}, f"{tablo}.{kolon}"
