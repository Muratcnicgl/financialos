"""
BUG #104 — K2 kırmızı-çizgi insight dedup'ı. Stabil (kategori-bazlı) title sayesinde
aynı kategori tekrar yazılınca UPSERT ile GÜNCELLENİR (mükerrer insight birikmez).
Bu test dedup MEKANİZMASINI kilitler: aynı (type,title) iki yazım -> 1 satır, evidence artar.
"""
from __future__ import annotations

from app.models import CoachInsight
from app.coach_insights import _save_or_update_insight


def test_ayni_title_upsert_tek_satir(db_session, test_user):
    for i in range(3):
        _save_or_update_insight(
            db=db_session, user_id=test_user.id,
            insight_type="explicit_red_line",
            title="Ima edilen kirmizi cizgi [kart_kullanimi]",  # STABİL (kategori-bazlı)
            content=f"kanit {i}",
            confidence_basis="pattern_grounded",
            source_refs=[f"run:{i}"],
            is_supporting_evidence=True,
        )
    rows = db_session.query(CoachInsight).filter(
        CoachInsight.user_id == test_user.id,
        CoachInsight.insight_type == "explicit_red_line",
    ).all()
    assert len(rows) == 1, "stabil title 3 yazımda tek insight olmalı (dedup)"
    assert rows[0].evidence_count == 3


def test_farkli_kategori_ayri_insight(db_session, test_user):
    """Farklı kategori = farklı title = ayrı insight (beklenen)."""
    for cat in ("kart_kullanimi", "kredi_taksiti"):
        _save_or_update_insight(
            db=db_session, user_id=test_user.id,
            insight_type="explicit_red_line",
            title=f"Ima edilen kirmizi cizgi [{cat}]",
            content="x",
            confidence_basis="pattern_grounded",
            source_refs=["r"],
            is_supporting_evidence=True,
        )
    rows = db_session.query(CoachInsight).filter(
        CoachInsight.user_id == test_user.id,
        CoachInsight.insight_type == "explicit_red_line",
    ).all()
    assert len(rows) == 2
