"""
M92 (Wave-7, Blok D) — Postgres'in dokunduğu veri-katmanı borcu: ORDER BY NULL-sıralaması dialect divergence.

R3 AYIKLAMA sonucu: 273 backlog'daki DATA maddelerinin çoğu ya M50-M53'te kapandı (enum/boolean/batch/numeric),
ya saf-hijyen (index/dual-index — sonuç değişmez), ya iki-dialect-eşit (CHECK/soft-delete). GERÇEK Postgres-davranış-
değiştiren TEK bulgu: `ORDER BY <col> DESC` NULL sıralaması dialect'e göre FARKLI —
  SQLite: NULL'lar DESC'te SONA · PostgreSQL: NULL'lar DESC'te BAŞA.
`get_active_insights_for_prompt` (koç prompt'una Top-5 insight enjekte eder) `sort_priority.desc()` kullanıyordu
(nullslast'siz) → Postgres'te NULL-öncelikli insight'lar YANLIŞ olarak başa sıralanıp koça farklı insight enjekte
edilirdi. Fix: `.desc().nullslast()` (iki dialect hizalandı; format_insights_for_prompt zaten böyleydi).

Bu test aynı insight setini iki dialect'te sıralayıp AYNI sırayı (NULL-priority SONA) kanıtlar.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, CoachInsight
from app.coach_insights import get_active_insights_for_prompt
from tests.pg_gate import postgres_url_or_skip, fresh_pg_database


def _seed_and_order(url, **kw):
    from sqlalchemy import text
    eng = create_engine(url, **kw)
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    try:
        from datetime import datetime
        db.add(User(id=1, name="m", email="m@x.com")); db.commit()
        # sort_priority NOT NULL (default 5) → hep eşit veriyoruz; ikincil sıralama last_seen_at
        # (NULLABLE) üzerinden. last_seen_at DESC nullslast: dated önce, NULL SONA (iki dialect'te de).
        db.add_all([
            CoachInsight(user_id=1, content="seen-yeni", status="active", sort_priority=5,
                         last_seen_at=datetime(2026, 7, 17)),
            CoachInsight(user_id=1, content="NULL-a", status="active", sort_priority=5, last_seen_at=None),
            CoachInsight(user_id=1, content="seen-eski", status="active", sort_priority=5,
                         last_seen_at=datetime(2026, 7, 10)),
            CoachInsight(user_id=1, content="NULL-b", status="active", sort_priority=5, last_seen_at=None),
        ])
        db.commit()
        rows = get_active_insights_for_prompt(db, 1, limit=10)
        return [r.content for r in rows]
    finally:
        db.close(); eng.dispose()


def test_null_ordering_iki_dialect_ayni():
    sqlite_order = _seed_and_order("sqlite:///:memory:",
                                   connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # yüksek-öncelik önce, NULL'lar SONDA
    assert sqlite_order[:2] == ["seen-yeni", "seen-eski"], f"SQLite sırası beklenmedik: {sqlite_order}"
    assert set(sqlite_order[2:]) == {"NULL-a", "NULL-b"}, f"NULL last_seen sonda değil: {sqlite_order}"

    pg_url = fresh_pg_database(postgres_url_or_skip(), "fos_nullorder")
    pg_order = _seed_and_order(pg_url)
    # Postgres AYNI sırayı vermeli (fix öncesi NULL'lar başa gelirdi)
    assert pg_order[:2] == ["seen-yeni", "seen-eski"], f"Postgres NULL-sıralaması fixsiz: {pg_order}"
    assert set(pg_order[2:]) == {"NULL-a", "NULL-b"}
    # iki dialect ilk-2 (non-null) sırası birebir aynı
    assert sqlite_order[:2] == pg_order[:2]
