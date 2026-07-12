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
