"""
DATA-005 / BUG #391 KAPISI — `setup_data` create_all SONRASI ALEMBIC DAMGASI YAZMIYORDU.

Ölçülen (11 Eyl 2026): `scripts/setup_data.py` şemayı `drop_all + create_all` ile kurar;
`alembic_version` yazılmaz. `baslat.ps1` her açılışta göç durumunu ölçer ve gerekirse
`alembic upgrade head` koşar → damgasız bir DB'de bu "table already exists" ile düşer
(ADR-013'ün yasakladığı belirsizlik; `app/database.py` BUG #311 notu aynı sınıfı anlatır).
Madde 60+ gündür "kısmen": create_all kaldırılmıştı ama damga hiç eklenmemişti.

Kilitlenen: `head_damgala(engine)` create_all şemasını head ile damgalar; `setup_data`
create_all'dan hemen SONRA onu çağırır (kaynak sırası ölçülür).
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

from app import schema_guard
from app.models import Base

KOK = Path(__file__).resolve().parent.parent


def test_create_all_semasi_head_ile_damgalanir(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    Base.metadata.create_all(eng)
    assert schema_guard._db_surumu(eng) is None, "create_all damga yazmamalı — ön koşul"
    rev = schema_guard.head_damgala(eng)
    assert rev == schema_guard._kod_head() and rev
    assert schema_guard._db_surumu(eng) == rev
    # idempotent
    assert schema_guard.head_damgala(eng) == rev
    assert schema_guard.validate_schema_version(eng) == "guncel"


def test_setup_data_create_all_dan_sonra_damgalar():
    kaynak = (KOK / "scripts" / "setup_data.py").read_text(encoding="utf-8")
    i = kaynak.find("Base.metadata.create_all(")
    j = kaynak.find("head_damgala(engine)")
    assert i > 0 and j > i, "setup_data create_all'dan SONRA head_damgala çağırmalı"
    assert "SessionLocal()" in kaynak[j:], "damga veri yüklenmeden önce olmalı"
