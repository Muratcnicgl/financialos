"""
Ortak datetime serileştirme yardımcıları (BUG #092 — per-file denetim tzinfo bulgusu).

Proje kuralı: DB'deki tüm datetime alanları timezone-naive UTC. Frontend'e serialize
ederken +00:00 (UTC) suffix'i EKLENMELİ; aksi halde Pydantic suffix'siz ISO string yayar,
JS bunu yerel saat sanıp Türkiye'de -3 saat kaymış gösterir (bkz. app/PROJE.md,
referans pattern: _memory_to_history_item).

Bu modül iki kullanım sunar:
- `utc_isoformat(dt)`: manuel dict serializer'lar için (örn. _txn_to_dict).
- `UtcDateTime`: Pydantic Out şemalarında `created_at: Optional[UtcDateTime]` olarak
  kullanılır; JSON serilaştırmada otomatik +00:00 ekler. Naive değeri UTC kabul eder,
  zaten aware olanı olduğu gibi bırakır (çift dönüşüm yok).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from pydantic import PlainSerializer


def utc_isoformat(dt: Optional[datetime]) -> Optional[str]:
    """Naive-UTC (veya aware) datetime -> +00:00 suffix'li ISO string. None -> None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# Pydantic V2: JSON serileştirmede UTC suffix'i garanti eden yeniden-kullanılabilir tip.
UtcDateTime = Annotated[
    datetime,
    PlainSerializer(utc_isoformat, return_type=str, when_used="json"),
]


def export_user_data(user, db) -> dict:
    """
    M11 (ADR-033 / KVKK taşınabilirlik): kullanıcının tüm verisini JSON-serileştir.
    Basit, tam kapsam: ilişkili tabloları satır-satır dict'e çevirir (SQLAlchemy sütunları).
    """
    from sqlalchemy import inspect as _sa_inspect

    def _row(obj) -> dict:
        out = {}
        for col in _sa_inspect(obj).mapper.column_attrs:
            val = getattr(obj, col.key)
            if isinstance(val, datetime):
                val = utc_isoformat(val)
            else:
                # Decimal/enum/date → JSON-güvenli
                try:
                    import json as _json
                    _json.dumps(val)
                except (TypeError, ValueError):
                    val = str(val)
            out[col.key] = val
        return out

    data: dict = {
        "exported_at": utc_isoformat(datetime.now(timezone.utc)),
        "user": _row(user),
    }
    # User üzerindeki tüm relationship koleksiyonlarını dök
    for rel in _sa_inspect(user).mapper.relationships:
        try:
            related = getattr(user, rel.key)
        except Exception:
            continue
        if related is None:
            continue
        if rel.uselist:
            data[rel.key] = [_row(item) for item in related]
        else:
            data[rel.key] = _row(related)
    return data
