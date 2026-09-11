"""
BUG #222 (P0/P5) — CANLI ŞEMA KODUN GERİSİNDE KALIRSA SESSİZ KALMA.

Ne oldu: canlı kurulum (`data/financialos.db`) kodun beklediğinden **9 migration geride**
kalmıştı (`a1b2c3d4e5f6` → `e1f2a3b4c5d6`). `master_checkpoints.rule_type` kolonu yoktu ve
`enforce_user_rules` her aksiyon onayında bu kolonu sorguladığı için **koç yolundan yapılan
her onay 500 veriyordu**. Uygulama yine de açılıyor, sağlıklı görünüyor, `/api/health` yeşil
dönüyordu — kırıklık ancak kullanıcı bir aksiyonu onaylamaya çalışınca ortaya çıkıyordu.

Neden kapı yoktu: ADR-013 "şema yalnız Alembic" der ve `create_all` startup'tan kaldırıldı
(M87) — doğru karar. Ama "migration'ı çalıştırmayı unutma" adımını KİMSE denetlemiyordu.
Deploy runbook'unda yazılı olması yetmez (L8: belgelenen ≠ uygulanan).

Bu modül şemanın kod ile aynı sürümde olduğunu startup'ta doğrular:
  * `alembic_version` tablosu YOKSA → sessiz geç. Bu, test/`create_all` yoludur
    (in-memory DB'ler migration görmez) — geliştirmeyi kilitlemeyiz (L6).
  * Sürüm head ile aynıysa → sessiz geç.
  * Farklıysa → production'da RuntimeError (uygulama AÇILMAZ), dev'de gürültülü uyarı.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _kod_head() -> Optional[str]:
    """Migration script'lerinden beklenen head revizyonu (tek head varsayımı)."""
    try:
        from pathlib import Path
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        kok = Path(__file__).resolve().parent.parent
        cfg = Config(str(kok / "alembic.ini"))
        cfg.set_main_option("script_location", str(kok / "alembic"))
        headler = ScriptDirectory.from_config(cfg).get_heads()
        return headler[0] if len(headler) == 1 else None
    except Exception as e:  # alembic yoksa/okunamıyorsa kapıyı kilitleme
        logger.warning("[schema] beklenen head okunamadı: %s: %s", type(e).__name__, e)
        return None


def head_damgala(engine) -> Optional[str]:
    """`create_all` ile kurulmuş bir şemayı alembic head'iyle damgalar (BUG #391 / DATA-005).

    `create_all` tabloları kurar ama `alembic_version`'ı yazmaz; sonraki `upgrade head`
    ya "table already exists" der ya da belirsizliğe düşer (ADR-013). Şemayı create_all
    ile kuran tek meşru yol `scripts/setup_data` (demo/test verisi) — o yol da bittiğinde
    burayı çağırır ki DB, alembic'in gözünde "güncel" olsun. Döner: damgalanan revizyon,
    head okunamazsa None (damga yapılmaz; sessiz yanlış damga, damgasızlıktan kötüdür).
    """
    head = _kod_head()
    if head is None:
        return None
    from pathlib import Path
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    kok = Path(__file__).resolve().parent.parent
    cfg = Config(str(kok / "alembic.ini"))
    cfg.set_main_option("script_location", str(kok / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    with engine.begin() as baglanti:
        MigrationContext.configure(baglanti).stamp(script, "head")
    return head


def _db_surumu(engine) -> Optional[str]:
    """DB'deki uygulanmış revizyon; `alembic_version` tablosu yoksa None."""
    from sqlalchemy import inspect, text

    if not inspect(engine).has_table("alembic_version"):
        return None
    with engine.connect() as baglanti:
        satir = baglanti.execute(text("select version_num from alembic_version")).fetchone()
    return satir[0] if satir else None


def validate_schema_version(engine=None) -> str:
    """Şema sürümü kod ile uyuşmuyorsa production'da fail-fast, dev'de uyarı.

    Test/`create_all` yolunda (alembic_version tablosu yok) hiçbir şey yapmaz.

    Döner: `"guncel"` | `"atlandi"` | `"uyumsuz"` (dev). Dönüş değeri bilinçli — kapının
    hangi dalda çalıştığı LOG'a bakmadan sınanabilsin. (Log'a dayanan test, uygulama
    logging yapılandırması değişince sessizce körleşiyordu.)
    """
    if engine is None:
        from app.database import engine as varsayilan_engine
        engine = varsayilan_engine

    beklenen = _kod_head()
    if beklenen is None:
        return "atlandi"

    mevcut = _db_surumu(engine)
    if mevcut is None:
        logger.info("[schema] alembic_version yok (test/create_all yolu) — sürüm kapısı atlandı.")
        return "atlandi"

    if mevcut == beklenen:
        logger.info("[schema] sürüm güncel: %s", mevcut)
        return "guncel"

    mesaj = (
        f"Veritabanı şeması KOD İLE UYUŞMUYOR: DB={mevcut}, kod={beklenen}. "
        f"Migration çalıştırılmamış — uygulama sessizce yarım çalışır (eksik kolonu okuyan "
        f"her uç 500 verir). Çözüm: `alembic upgrade head`."
    )
    from app.settings import is_production

    if is_production():
        raise RuntimeError(mesaj)
    logger.warning("[schema] %s", mesaj)
    return "uyumsuz"
