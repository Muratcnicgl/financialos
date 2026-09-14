"""
PERF-011 (BUG #491): birincil anahtar üstünde ikinci bir indeks yaşamaz.

Ölçüm (14 Eyl 2026): 29 tabloda `primary_key=True, index=True` — her biri için PK'nın yanına
`ix_<tablo>_id` üretiliyordu (canlı SQLite'ta 29 adet). PK zaten benzersiz indekstir; ikinci
indeks her yazımda maliyet, hiç okuma kazancı yok. Kilitlenen:
  1. modelde hiçbir PK sütunu `index=True` taşımaz (metadata: `id` üstünde tekil indeks yok),
  2. göç `head`e yükseltilmiş taze DB'de `ix_*_id` indeksi yok,
  3. göç listesi modeldeki tablo kümesini kapsar (yeni tablo `index=True` ile gelirse 1 yakalar).
"""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.models import Base

KOK = Path(__file__).resolve().parent.parent


def test_modelde_pk_ustunde_ikinci_indeks_yok():
    src = (KOK / "app" / "models.py").read_text(encoding="utf-8")
    assert "primary_key=True, index=True" not in src
    kirli = []
    for tablo in Base.metadata.tables.values():
        pk = [c.name for c in tablo.primary_key.columns]
        for ix in tablo.indexes:
            if [c.name for c in ix.columns] == pk:
                kirli.append(f"{tablo.name}.{ix.name}")
    assert not kirli, f"PK ile aynı sütunda ikinci indeks: {kirli}"


def test_taze_dbde_pk_indeksi_yok(tmp_path):
    from alembic import command
    from alembic.config import Config

    yol = tmp_path / "t.db"
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{yol.as_posix()}")
    command.upgrade(cfg, "head")
    eng = create_engine(f"sqlite:///{yol.as_posix()}")
    insp = inspect(eng)
    fazla = [ix["name"] for t in insp.get_table_names() for ix in insp.get_indexes(t) if re.fullmatch(rf"ix_{t}_id", ix["name"] or "")]
    assert fazla == [], f"taze DB'de PK indeksi: {fazla}"


def test_goc_listesi_model_tablolarini_kapsar():
    import importlib.util
    yol = KOK / "alembic" / "versions" / "e9f0a1b2c3d4_pk_indeks_temizligi.py"
    spec = importlib.util.spec_from_file_location("goc_pk", yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    model_tablolari = {t for t, tab in Base.metadata.tables.items() if [c.name for c in tab.primary_key.columns] == ["id"]}
    assert model_tablolari <= set(mod.TABLOLAR), f"göç listesinde eksik tablo: {model_tablolari - set(mod.TABLOLAR)}"
