"""
BUG #092 — datetime UTC suffix serileştirme testi.
Naive-UTC datetime frontend'e +00:00 suffix'li gitmeli (yoksa JS -3h kayar).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from app.serializers import utc_isoformat, UtcDateTime


def test_utc_isoformat_naive():
    dt = datetime(2026, 5, 1, 12, 0, 0)  # naive
    out = utc_isoformat(dt)
    assert out.endswith("+00:00"), out


def test_utc_isoformat_none():
    assert utc_isoformat(None) is None


def test_utc_isoformat_zaten_aware_bozulmaz():
    dt = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    out = utc_isoformat(dt)
    assert out.endswith("+00:00")
    assert out.count("+00:00") == 1  # çift dönüşüm yok


def test_pydantic_utcdatetime_json_suffix():
    class M(BaseModel):
        created_at: UtcDateTime
        resolved_at: Optional[UtcDateTime] = None

    m = M(created_at=datetime(2026, 5, 1, 9, 30, 0))  # naive-UTC
    data = m.model_dump(mode="json")
    assert data["created_at"].endswith("+00:00"), data["created_at"]
    assert data["resolved_at"] is None
