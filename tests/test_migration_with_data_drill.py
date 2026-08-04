"""
P5 (Wave-9) — BUG #196: migration provası YALNIZ TEMİZ DB üzerindeydi + env.py izolasyonu.

İki ayrı sorun:

(a) `scripts/test_fresh_db_migration.py` BOŞ bir veritabanında `upgrade head` koşuyordu.
    Production'da migration **VERİ DOLUYKEN** çalışır (docker-entrypoint her açılışta
    `alembic upgrade head` yapar). Temiz DB'de geçen bir migration, dolu DB'de NOT NULL
    varsayılanı olmayan kolon veya benzersizlik ihlaliyle patlayabilir.

(b) Bu provayı yazmak MÜMKÜN DEĞİLDİ: `alembic/env.py` kendisine verilen `sqlalchemy.url`'i
    koşulsuz yok sayıp uygulamanın motorunu kullanıyordu → test içinden `command.upgrade`
    GERÇEK veritabanına gidiyordu (canlı veri üstünde sessiz şema değişikliği riski).
    Düzeltildi: config'te açık URL varsa O kullanılır.

Bu dosya hem tatbikatı koşar hem izolasyonu (gerçek DB'ye dokunulmadığını) kanıtlar.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

_ROOT = Path(__file__).resolve().parent.parent

# Bu turda eklenen migration'lardan ÖNCEKİ sürüm — "eski canlı DB"nin temsili
ESKI_SURUM = "a1b2c3d4e5f6"


def _cfg(db_url: str) -> Config:
    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)   # BUG #196: artık DİKKATE ALINIR
    return cfg


@pytest.fixture
def dolu_eski_db(tmp_path):
    """Eski şema + gerçek kullanıcı verisi (canlı DB'nin temsili, İZOLE dosya)."""
    dosya = tmp_path / "canli_temsil.db"
    url = f"sqlite:///{dosya.as_posix()}"
    command.upgrade(_cfg(url), ESKI_SURUM)

    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("INSERT INTO users (id, name, email, is_active) "
                       "VALUES (1, 'Kullanici', 'a@example.com', 1)"))
        c.execute(text("INSERT INTO accounts (id, user_id, name, account_type, balance, is_emanet) "
                       "VALUES (1, 1, 'Maas Hesabim', 'cash', 12345.6700, 0)"))
        c.execute(text("INSERT INTO master_checkpoints "
                       "(id, user_id, title, description, checkpoint_type, priority, "
                       "is_active, is_system) "
                       "VALUES (1, 1, 'Acil fon', 'dokunma', 'red_line', 1, 1, 0)"))
    eng.dispose()
    return url, dosya


def test_dolu_dbde_head_e_yukseltme_calisir(dolu_eski_db):
    """Migration zinciri veri doluyken de sonuna kadar koşmalı (deploy'un yaptığı iş)."""
    url, _dosya = dolu_eski_db
    command.upgrade(_cfg(url), "head")   # patlarsa test kırılır

    eng = create_engine(url)
    with eng.connect() as c:
        surum = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
    eng.dispose()
    assert surum and surum != ESKI_SURUM, f"Sürüm ilerlemedi: {surum}"


def test_yukseltme_veriyi_korur(dolu_eski_db):
    """En kritik güvence: migration kullanıcının parasını/kayıtlarını BOZMAZ."""
    url, _dosya = dolu_eski_db
    command.upgrade(_cfg(url), "head")

    eng = create_engine(url)
    with eng.connect() as c:
        hesap = c.execute(text("SELECT name, balance FROM accounts WHERE id=1")).fetchone()
        kural = c.execute(text("SELECT title FROM master_checkpoints WHERE id=1")).fetchone()
        eposta = c.execute(text("SELECT email FROM users WHERE id=1")).scalar()
    eng.dispose()

    assert hesap[0] == "Maas Hesabim"
    assert float(hesap[1]) == pytest.approx(12345.67), "Bakiye migration'da değişti!"
    assert kural[0] == "Acil fon"
    assert eposta == "a@example.com"


def test_yeni_kolonlar_eski_satirlarda_guvenli(dolu_eski_db):
    """Yeni kolonlar ESKİ satırlarda güvenli varsayılan almalı (NOT NULL patlaması yok)."""
    url, _dosya = dolu_eski_db
    command.upgrade(_cfg(url), "head")

    eng = create_engine(url)
    with eng.connect() as c:
        tv = c.execute(text("SELECT token_version FROM users WHERE id=1")).scalar()
        rt = c.execute(text("SELECT rule_type FROM master_checkpoints WHERE id=1")).scalar()
        tablolar = {r[0] for r in c.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"))}
    eng.dispose()

    assert tv == 0, f"token_version eski satırda güvenli varsayılan almadı: {tv}"
    assert rt is None, "rule_type eski satırda NULL olmalı (serbest metin kural bozulmaz)"
    for yeni in ("rate_limit_hits", "demo_data_markers", "error_logs"):
        assert yeni in tablolar, f"{yeni} tablosu yükseltmede oluşmadı"


def test_prova_gercek_veritabanina_DOKUNMAZ(dolu_eski_db):
    """BUG #196 kilidi: config'te URL verildiyse migration O DB'ye gitmeli.

    Bu test olmasaydı, tatbikat sessizce CANLI veritabanını yükseltirdi.
    """
    url, dosya = dolu_eski_db
    gercek = _ROOT / "data" / "financialos.db"
    onceki = gercek.stat().st_mtime if gercek.exists() else None

    command.upgrade(_cfg(url), "head")

    assert dosya.exists() and dosya.stat().st_size > 0, "İzole DB yazılmadı"
    if onceki is not None:
        assert gercek.stat().st_mtime == onceki, (
            "Migration GERÇEK veritabanına dokundu — env.py izolasyonu kırık (BUG #196)"
        )
