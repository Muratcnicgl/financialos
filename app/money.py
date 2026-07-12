"""
Para / Decimal yardımcıları (ADR-030).

Para alanları DB'de `Numeric(19,4)` → ORM `Decimal` döner. Aritmetik `Decimal + float`
`TypeError` verir (sessiz-yanlış değil, sert çökme — iyi). Bu modül tek coercion noktası:
gerçek-float büyüklükleri (lot adedi, faiz oranı, enflasyon faktörü, gün kesri) para
Decimal'iyle çarpılırken `D()` ile Decimal'e çekilir. Para matematiği ROUND_HALF_UP,
prec=28 (Beancount/Maybe Finance çizgisi). JSON serialize Pydantic Decimal→float default.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Optional, Union

getcontext().prec = 28  # ADR-030: para için yeterli anlamlı basamak

ZERO = Decimal("0")
Number = Union[int, float, Decimal, str, None]


def D(x: Number) -> Optional[Decimal]:
    """Herhangi bir sayıyı güvenle Decimal'e çevir (float ise str üzerinden — binary drift yok). None→None."""
    if x is None:
        return None
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def q2(x: Number) -> Optional[Decimal]:
    """2 ondalığa yuvarla (TL kuruş), ROUND_HALF_UP. None→None."""
    d = D(x)
    return None if d is None else d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def q4(x: Number) -> Optional[Decimal]:
    """4 ondalığa yuvarla (fiyat/hassas), ROUND_HALF_UP. None→None."""
    d = D(x)
    return None if d is None else d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def floatify(obj):
    """
    SERIALIZE SINIRI (ADR-030 / B1): iç aritmetik Decimal (kesin) yapılır; ama public dönüş
    (cockpit dict, simülasyon, HTTP payload) `float`'a çevrilir → JSON float serialize, frontend
    değişmez, formatTL aynı. Decimal DEPO+HESAP içindir, TAŞIMA float. Dict/list'i özyinelemeli gezer.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: floatify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [floatify(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(floatify(v) for v in obj)
    return obj
