"""
P9 (Wave-9) — BUG #208: GERİ ALMA (rollback) provası yoktu.

Runbook'ta geri alma yalnız `git reset --hard <tag>` + rebuild olarak yazılıydı. Ama kötü
bir sürüm canlıya çıktığında **şema zaten ilerlemiş** olur: eski kod yeni şemayla açılır mı,
`alembic downgrade` veriyi bozar mı — hiç denenmemişti. "Geri alabiliriz" iddiası, ilk kez
gerçek olayda (panik anında, canlı veriyle) sınanacaktı.

Bu tatbikat: head'e kadar kur → gerçek veri yaz → BİR SÜRÜM GERİ AL → verinin durduğunu
doğrula → tekrar head'e çık. Ayrıca ileriye dönük kapı: Wave-9 ve sonrası her migration
GERÇEK bir downgrade gövdesi taşımalı (yoksa o sürüm geri alınamaz).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

_ROOT = Path(__file__).resolve().parent.parent

# BUG #248 (D38): kapı eskiden ELLE yazılmış bir revizyon kümesine bakıyordu — yani listeye
# eklenmeyen HER YENİ migration denetlenmiyordu ve `def downgrade(): pass` yazan biri kapıdan
# sessizce geçiyordu (o migration'da `alembic downgrade` BAŞARIYLA döner, şema geride kalır,
# alembic_version geriye yazılır → "geri alabiliriz" iddiası canlıda yalan olur). Artık liste
# ŞEMADAN türetilir: `alembic/versions` altındaki her revizyon denetlenir; yalnız aşağıdaki
# BİLİNEN-ESKİ sürümler gerekçeyle muaftır (baseline/veri-taşıma; geri alınacak DDL'leri yok).
ESKI_ISTISNALAR = {
    "fa46373f4ca8": "baseline (mevcut şemanın fotoğrafı — geri alınacak DDL yok)",
    "62136ecd252e": "erken şema düzeltmesi (Wave-2 öncesi)",
    "12b80d6485bf": "erken şema düzeltmesi (Wave-2 öncesi)",
    "9558e190f209": "erken şema düzeltmesi (Wave-2 öncesi)",
    "0db7cfbb706f": "erken şema düzeltmesi (Wave-2 öncesi)",
    "53a3257f906c": "erken şema düzeltmesi (Wave-2 öncesi)",
    "fb38814500bf": "goal engine (Wave-3, veri taşıma ağırlıklı)",
    "f3dda4d3996d": "goal engine baseline (Wave-3)",
    "fec73e5343e5": "envelope/wishlist (Wave-3)",
    "c1d2e3f4a5b6": "yetim tmp_users temizliği (veri taşıma — geri alınacak şey yok)",
}


def _tum_revizyonlar() -> list[str]:
    script = ScriptDirectory.from_config(_cfg("sqlite:///:memory:"))
    return sorted(r.revision for r in script.walk_revisions())




def _cfg(db_url: str) -> Config:
    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)   # BUG #196: dikkate alınır
    return cfg


@pytest.fixture
def head_db(tmp_path):
    """head şeması + gerçek kullanıcı verisi."""
    dosya = tmp_path / "rollback.db"
    url = f"sqlite:///{dosya.as_posix()}"
    command.upgrade(_cfg(url), "head")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("INSERT INTO users (id, name, email, is_active, token_version) "
                       "VALUES (1, 'Kullanici', 'a@example.com', 1, 0)"))
        c.execute(text("INSERT INTO accounts (id, user_id, name, account_type, balance, is_emanet) "
                       "VALUES (1, 1, 'Maas Hesabim', 'cash', 9876.5400, 0)"))
    eng.dispose()
    return url


def test_bir_surum_geri_alinabilir_ve_veri_durur(head_db):
    """Kötü sürüm senaryosu: son migration geri alınır, kullanıcı verisi BOZULMAZ."""
    command.downgrade(_cfg(head_db), "-1")

    eng = create_engine(head_db)
    with eng.connect() as c:
        satir = c.execute(text("SELECT name, balance FROM accounts WHERE id=1")).fetchone()
    eng.dispose()
    assert satir[0] == "Maas Hesabim"
    assert float(satir[1]) == pytest.approx(9876.54), "Geri almada bakiye bozuldu"


def test_geri_alma_sonrasi_tekrar_head_e_cikilabilir(head_db):
    """Düzeltme yayınlandığında ileri gidiş yine çalışmalı (tek yönlü kapı olmasın)."""
    command.downgrade(_cfg(head_db), "-1")
    command.upgrade(_cfg(head_db), "head")

    eng = create_engine(head_db)
    with eng.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM accounts")).scalar()
        tablolar = {r[0] for r in c.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"))}
    eng.dispose()
    assert n == 1
    assert "scheduler_runs" in tablolar


def test_uc_surum_geri_alinabilir(head_db):
    """Birden fazla sürüm geri alma (kötü sürüm zinciri) da çalışmalı."""
    command.downgrade(_cfg(head_db), "-3")
    eng = create_engine(head_db)
    with eng.connect() as c:
        satir = c.execute(text("SELECT name FROM accounts WHERE id=1")).fetchone()
    eng.dispose()
    assert satir[0] == "Maas Hesabim"


def test_kapsam_tabani_revizyonlar_bulunuyor():
    """L23: tarama boş dönerse alttaki kapı sessizce 'her şey yolunda' der."""
    hepsi = _tum_revizyonlar()
    assert len(hepsi) >= 15, f"Yalnız {len(hepsi)} revizyon bulundu — tarama bozuk"
    assert set(ESKI_ISTISNALAR) <= set(hepsi), (
        f"İstisna listesinde artık var olmayan revizyon: {sorted(set(ESKI_ISTISNALAR) - set(hepsi))}"
    )


@pytest.mark.parametrize("revizyon", [r for r in _tum_revizyonlar()])
def test_yeni_migrationlar_gercek_downgrade_tasir(revizyon):
    """İleriye dönük kapı: downgrade'i `pass` olan sürüm GERİ ALINAMAZ."""
    if revizyon in ESKI_ISTISNALAR:
        pytest.skip(f"bilinen-eski istisna: {ESKI_ISTISNALAR[revizyon]}")
    script = ScriptDirectory.from_config(_cfg("sqlite:///:memory:"))
    rev = script.get_revision(revizyon)
    kaynak = Path(rev.path).read_text(encoding="utf-8")
    m = re.search(r"def downgrade\(\)[^:]*:(.*)", kaynak, re.S)
    assert m, f"{revizyon}: downgrade fonksiyonu yok"
    govde = [l.strip() for l in m.group(1).strip().splitlines()
             if l.strip() and not l.strip().startswith("#")]
    assert govde and govde != ["pass"], (
        f"{revizyon} ({Path(rev.path).name}): downgrade BOŞ — bu sürüm geri alınamaz"
    )


def test_runbook_geri_alma_adimini_migration_ile_birlikte_anlatir():
    """Geri alma yalnız 'git reset' değildir: şema da geri alınmalı."""
    runbook = (_ROOT / "docs" / "deployment" / "runbook.md").read_text(encoding="utf-8").lower()
    assert "alembic downgrade" in runbook, (
        "Runbook geri almada ŞEMA adımını (alembic downgrade) anlatmıyor — "
        "eski kod yeni şemayla açılmaya çalışır"
    )
