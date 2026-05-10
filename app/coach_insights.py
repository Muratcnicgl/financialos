"""
app/coach_insights.py

Wave-2 Hafta 1 Davranissal Hafiza modulu.

Mimari (ADR-016 Saf Karma A):
- 8 deterministik extractor (Mustafa mimarisi)
- Hibrit tetikleme (D pattern): olay-tepki + esik-tepki + periyodik
- Honcho Dream paterni: explicit_red_line icin gece batch LLM consolidation
- Saf Karma A invalidation: counter_evidence_count >= 3 AND >= evidence_count/2

Yazim sirasi:
1. decision_rhythm (BU DOSYA - en sade, saf zaman dagilimi)
2. mc_reference_frequency
3. question_typology
4. category_account_preference
5. action_rejection_pattern
6. breakthrough
7. setback
8. explicit_red_line K1 (regex)
9. explicit_red_line K2 (Honcho Dream batch LLM)

Adaptasyon notu (mevcut model uyumu):
- ActionHistory.applied_at kullanilir (created_at yok)
- ActionHistory.success == True filtresi (status alani yok)
- CoachInsight.sort_priority Integer (priority InsightPriority enum'u eski kod icin korunur)
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Iterator, Literal, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

import re
from collections import Counter

from app.models import (
    CoachInsight,
    Transaction,
    ActionHistory,
    CoachMemory,
    PendingAction,
    Account,
    MasterCheckpoint,
)

logger = logging.getLogger(__name__)


# ============================================================
# BOLUM 1: SABITLER & TIPLER
# ============================================================

InsightType = Literal[
    "action_rejection_pattern",
    "category_account_preference",
    "explicit_red_line",
    "breakthrough",
    "setback",
    "mc_reference_frequency",
    "question_typology",
    "decision_rhythm",
]

ConfidenceBasis = Literal["data_grounded", "mc_rule", "pattern_grounded"]
ParaCategory = Literal["project", "area", "resource", "archive"]

# Saf Karma A invalidation esikleri
INVALIDATION_COUNTER_MIN = 3
INVALIDATION_COUNTER_RATIO = 0.5
DORMANT_DAYS = 90

# decision_rhythm sabitleri
DECISION_RHYTHM_LOOKBACK_DAYS = 30
DECISION_RHYTHM_MIN_ACTIONS = 5
DECISION_RHYTHM_DOMINANT_RATIO = 0.40

# Saat dilimleri (chronotype literature)
TIME_SLOTS = {
    "gece":  (0, 6),
    "sabah": (6, 12),
    "ogle":  (12, 18),
    "aksam": (18, 24),
}

TIME_SLOT_LABELS_TR = {
    "gece":  "gece (00:00-06:00)",
    "sabah": "sabah (06:00-12:00)",
    "ogle":  "oglen (12:00-18:00)",
    "aksam": "aksam (18:00-24:00)",
}


# ============================================================
# BOLUM 2: YARDIMCI FONKSIYONLAR
# ============================================================

@contextmanager
def extractor_telemetry(extractor_name: str, user_id: int) -> Iterator[logging.LoggerAdapter]:
    """
    Her extractor calismasini structured logging + hata yutma + sure olcumu icinde sarar.
    Bir extractor coker ise log'a yazilir, raise edilmez -> diger extractor'lar devam eder.
    BUG #036 paterni (sessiz fail) yerine LOUDLY FAIL paterni.
    """
    start = datetime.now(timezone.utc)
    extra = {"extractor": extractor_name, "user_id": user_id}
    log = logging.LoggerAdapter(logger, extra)
    log.info(f"[{extractor_name}] started for user_id={user_id}")

    try:
        yield log
    except Exception as e:
        log.error(
            f"[{extractor_name}] FAILED for user_id={user_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
    finally:
        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        log.info(f"[{extractor_name}] completed in {duration_ms:.1f}ms")


def _save_or_update_insight(
    db: Session,
    user_id: int,
    insight_type: InsightType,
    title: str,
    content: str,
    confidence_basis: ConfidenceBasis,
    source_refs: list[str],
    is_supporting_evidence: bool = True,
    para_category: ParaCategory = "area",
    priority: int = 5,
) -> None:
    """
    Insight'i UPSERT eder. UNIQUE(user_id, insight_type, title) constraint kullanir.
    SQLite ON CONFLICT DO UPDATE - race condition korumali, atomic.
    Saf Karma A invalidation kontrolu kayittan sonra otomatik yapilir.
    """
    now = datetime.utcnow()  # DB alanlari timezone-naive UTC
    source_refs_json = json.dumps(source_refs, ensure_ascii=False)

    if is_supporting_evidence:
        evidence_increment = 1
        counter_increment = 0
        last_ev = now
        last_co = None
    else:
        evidence_increment = 0
        counter_increment = 1
        last_ev = None
        last_co = now

    stmt = sqlite_insert(CoachInsight).values(
        user_id=user_id,
        insight_type=insight_type,
        title=title,
        content=content,
        confidence_basis=confidence_basis,
        source_refs=source_refs_json,
        evidence_count=evidence_increment if is_supporting_evidence else 0,
        counter_evidence_count=counter_increment if not is_supporting_evidence else 0,
        last_evidence_at=last_ev,
        last_counter_at=last_co,
        status="active",
        activated_at=now,
        last_seen_at=now,
        para_category=para_category,
        sort_priority=priority,
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "insight_type", "title"],
        set_={
            "content": stmt.excluded.content,
            "evidence_count": CoachInsight.evidence_count + evidence_increment,
            "counter_evidence_count": CoachInsight.counter_evidence_count + counter_increment,
            "last_evidence_at": last_ev if is_supporting_evidence else CoachInsight.last_evidence_at,
            "last_counter_at": last_co if not is_supporting_evidence else CoachInsight.last_counter_at,
            "last_seen_at": now,
            "source_refs": stmt.excluded.source_refs,
            "sort_priority": stmt.excluded.sort_priority,
        },
    )

    db.execute(stmt)
    db.commit()

    _check_and_invalidate(db, user_id, insight_type, title)


def _check_and_invalidate(
    db: Session,
    user_id: int,
    insight_type: InsightType,
    title: str,
) -> None:
    """
    Saf Karma A kurali kontrolu:
    counter_evidence_count >= 3 AND counter >= evidence/2 -> status='invalidated'
    """
    insight = db.execute(
        select(CoachInsight).where(
            and_(
                CoachInsight.user_id == user_id,
                CoachInsight.insight_type == insight_type,
                CoachInsight.title == title,
                CoachInsight.status == "active",
            )
        )
    ).scalar_one_or_none()

    if insight is None:
        return

    if (
        insight.counter_evidence_count >= INVALIDATION_COUNTER_MIN
        and insight.counter_evidence_count >= insight.evidence_count * INVALIDATION_COUNTER_RATIO
    ):
        insight.status = "invalidated"
        insight.archived_at = datetime.utcnow()
        insight.archived_reason = "data_changed"
        db.commit()
        logger.info(
            f"[invalidation] user_id={user_id} insight '{title}' "
            f"invalidated (evidence={insight.evidence_count}, "
            f"counter={insight.counter_evidence_count})"
        )


def get_active_insights_for_prompt(
    db: Session, user_id: int, limit: int = 5
) -> list[CoachInsight]:
    """
    V3_GOD_MODE_PROMPT 'DAVRANISSAL HAFIZA' bolumune enjekte edilecek insight'lar.
    Filtre: status='active', siralama: sort_priority DESC, last_seen_at DESC, limit 5.
    """
    return (
        db.execute(
            select(CoachInsight)
            .where(
                CoachInsight.user_id == user_id,
                CoachInsight.status == "active",
            )
            .order_by(
                CoachInsight.sort_priority.desc(),
                CoachInsight.last_seen_at.desc(),
            )
            .limit(limit)
        )
        .scalars()
        .all()
    )


# ============================================================
# BOLUM 3: EXTRACTOR'LAR
# ============================================================


def _classify_hour_to_slot(hour: int) -> str:
    """Saat 0-23 -> 'gece' | 'sabah' | 'ogle' | 'aksam'"""
    for slot, (start, end) in TIME_SLOTS.items():
        if start <= hour < end:
            return slot
    return "gece"


def extract_decision_rhythm(db: Session, user_id: int) -> None:
    """
    Extractor #8: decision_rhythm

    Tetikleyici: APScheduler gunde 1 (Hibrit C - lifespan startup veya 03:00 cron).

    Mantik:
    1. Son 30 gun action_history'deki basarili aksiyonlari al (success=True)
    2. Her aksiyonun saatini 4 dilime siniflandir (gece/sabah/ogle/aksam)
    3. Dominant dilim hesapla (>=%40 oraninda toplaniyor mu?)
    4. Eger dominant dilim varsa insight olustur/guncelle
    5. Yoksa - 'davranis dengeli' insight YAZMA (gurultu olur)

    Mustafa mimarisi: LLM yok, regex yok, saf SQL + istatistik.
    confidence_basis: 'pattern_grounded'

    Model notu: ActionHistory.applied_at (timezone-naive UTC) kullanilir.
    """
    with extractor_telemetry("decision_rhythm", user_id) as log:
        cutoff = datetime.utcnow() - timedelta(days=DECISION_RHYTHM_LOOKBACK_DAYS)

        actions = (
            db.execute(
                select(ActionHistory).where(
                    and_(
                        ActionHistory.user_id == user_id,
                        ActionHistory.applied_at >= cutoff,
                        ActionHistory.success == True,
                    )
                )
            )
            .scalars()
            .all()
        )

        if len(actions) < DECISION_RHYTHM_MIN_ACTIONS:
            log.info(
                f"insufficient sample: {len(actions)} actions "
                f"(min {DECISION_RHYTHM_MIN_ACTIONS}), skipping"
            )
            return

        slot_counts: dict[str, int] = {slot: 0 for slot in TIME_SLOTS.keys()}
        action_ids_per_slot: dict[str, list[int]] = {slot: [] for slot in TIME_SLOTS.keys()}

        for action in actions:
            # applied_at timezone-naive UTC -> local saate donustur
            local_dt = action.applied_at.replace(tzinfo=timezone.utc).astimezone()
            slot = _classify_hour_to_slot(local_dt.hour)
            slot_counts[slot] += 1
            action_ids_per_slot[slot].append(action.id)

        total = len(actions)

        dominant_slot = max(slot_counts, key=slot_counts.get)
        dominant_count = slot_counts[dominant_slot]
        dominant_ratio = dominant_count / total

        log.info(
            f"distribution: {slot_counts}, "
            f"dominant={dominant_slot} ({dominant_ratio:.0%})"
        )

        if dominant_ratio < DECISION_RHYTHM_DOMINANT_RATIO:
            log.info(
                f"no dominant slot (max ratio {dominant_ratio:.0%} < "
                f"{DECISION_RHYTHM_DOMINANT_RATIO:.0%}), skipping"
            )
            return

        slot_label = TIME_SLOT_LABELS_TR[dominant_slot]
        title = f"Buyuk kararlarin cogu {dominant_slot} dilminde"
        content = (
            f"Son {DECISION_RHYTHM_LOOKBACK_DAYS} gunde "
            f"{total} onaylanan aksiyonun {dominant_count}'i "
            f"({dominant_ratio:.0%}) {slot_label} araliginda alindi. "
            f"Bu zaman diliminin disinda alinan onemli kararlarda "
            f"daha dikkatli sorgulama yapilabilir."
        )

        source_refs = [
            f"action_history:{aid}"
            for aid in action_ids_per_slot[dominant_slot][:10]
        ]

        _save_or_update_insight(
            db=db,
            user_id=user_id,
            insight_type="decision_rhythm",
            title=title,
            content=content,
            confidence_basis="pattern_grounded",
            source_refs=source_refs,
            is_supporting_evidence=True,
            para_category="area",
            priority=4,
        )

        log.info(f"insight saved/updated: '{title}'")


# ============================================================
# EXTRACTOR 2/9: mc_reference_frequency
# ============================================================
# Mantik: Son 30 gun coach yanitlarinda (CoachMemory role='assistant')
# hangi MC numarasi kac kez gecti. En sik 3 MC -> aktif insight + sort_priority=10.
# Hic gecmemis MC'ler -> dormant insight (pattern_grounded, kanit eksikligi).
#
# Tetikleme: Periyodik (lifespan startup hook + APScheduler gece 03:00).
# Kategori: D Hibrit'te "Periyodik (6,7,8) gunde 1" gurubuyla ayni patern.
#
# Veri kaynagi notu: MC referanslari kodda yapilandirilmamis (mc_rules_applied
# JSON kolonu YOK). LLM yanit metninde "MC1".."MC8" formatinda gecer. Bu yuzden
# regex ile content alanini tarariz - prompt sablonu MC{n} formatini garantiler.

MC_REFERENCE_PATTERN = re.compile(r"\bMC([1-8])\b")
MC_REFERENCE_PERIOD_DAYS = 30
MC_REFERENCE_MIN_SAMPLE = 10  # En az 10 assistant mesaji olmali
MC_REFERENCE_TOP_K = 3        # En sik 3 MC dominant
MC_REFERENCE_DOMINANT_PRIORITY = 10  # sort_priority degeri


def _upsert_insight_absolute(
    db: Session,
    user_id: int,
    insight_type: str,
    title: str,
    content: str,
    confidence_basis: str,
    source_refs: dict,
    evidence_count: int,
    sort_priority: int,
    status: str,
) -> str:
    """
    Periyodik extractor'lar icin UPSERT. evidence_count direkt set edilir
    (inkremental degil). "created" veya "updated" doner.
    _save_or_update_insight'in inkremental mantigi bu use-case'e uymadigi icin ayri helper.
    """
    now = datetime.utcnow()
    source_refs_json = json.dumps(source_refs, ensure_ascii=False)

    existing = db.execute(
        select(CoachInsight).where(
            CoachInsight.user_id == user_id,
            CoachInsight.insight_type == insight_type,
            CoachInsight.title == title,
        )
    ).scalar_one_or_none()

    if existing is None:
        db.add(CoachInsight(
            user_id=user_id,
            insight_type=insight_type,
            title=title,
            content=content,
            confidence_basis=confidence_basis,
            source_refs=source_refs_json,
            evidence_count=evidence_count,
            counter_evidence_count=0,
            last_evidence_at=now if evidence_count > 0 else None,
            status=status,
            activated_at=now,
            last_seen_at=now,
            para_category="area",
            sort_priority=sort_priority,
        ))
        db.commit()
        return "created"

    existing.content = content
    existing.evidence_count = evidence_count
    existing.source_refs = source_refs_json
    existing.last_seen_at = now
    existing.sort_priority = sort_priority
    existing.status = status
    db.commit()
    return "updated"


def extract_mc_reference_frequency(db: Session, user_id: int) -> dict:
    """
    Son 30 gun coach yanitlarinda MC1..MC8 referans frekansini cikarir.

    Donus: {"created": int, "updated": int, "skipped_reason": str | None,
            "total_messages": int, "mc_counts": dict}
    """
    with extractor_telemetry("mc_reference_frequency", user_id=user_id):
        cutoff = datetime.utcnow() - timedelta(days=MC_REFERENCE_PERIOD_DAYS)

        assistant_messages = (
            db.query(CoachMemory)
            .filter(
                CoachMemory.user_id == user_id,
                CoachMemory.role == "assistant",
                CoachMemory.timestamp >= cutoff,
            )
            .all()
        )

        total = len(assistant_messages)

        if total < MC_REFERENCE_MIN_SAMPLE:
            return {
                "created": 0,
                "updated": 0,
                "skipped_reason": f"insufficient_sample ({total} < {MC_REFERENCE_MIN_SAMPLE})",
                "total_messages": total,
                "mc_counts": {},
            }

        # Regex ile MC numaralarini topla. Bir mesajda 3 kez MC8 gectiyse 3 say -
        # cunku LLM gercekten o kurali agir kullaniyor demek.
        counter: Counter = Counter()
        for msg in assistant_messages:
            if not msg.content:
                continue
            for match in MC_REFERENCE_PATTERN.findall(msg.content):
                counter[match] += 1

        # Tum MC'leri normalize et (1..8)
        mc_counts = {str(i): counter.get(str(i), 0) for i in range(1, 9)}

        # Top-K secimi - frekans azalan, esitlikte MC numarasi kucuk oncelikli
        ranked = sorted(
            mc_counts.items(),
            key=lambda kv: (-kv[1], int(kv[0])),
        )

        created = 0
        updated = 0

        # Dominant insight'lar (top 3, count > 0)
        for rank, (mc_num, count) in enumerate(ranked[:MC_REFERENCE_TOP_K], start=1):
            if count == 0:
                continue

            title = f"MC{mc_num} sik referans verilen kural"
            content = (
                f"Son {MC_REFERENCE_PERIOD_DAYS} gunde MC{mc_num} kurali "
                f"toplam {count} kez referans verildi (rank {rank}/{MC_REFERENCE_TOP_K}). "
                f"Bu kural su an aktif kullanimda."
            )
            source_refs = {
                "period_days": MC_REFERENCE_PERIOD_DAYS,
                "total_assistant_messages": total,
                "mc_counts": mc_counts,
                "rank": rank,
                "mc_number": int(mc_num),
            }

            result = _upsert_insight_absolute(
                db=db,
                user_id=user_id,
                insight_type="mc_reference_frequency",
                title=title,
                content=content,
                confidence_basis="pattern_grounded",
                source_refs=source_refs,
                evidence_count=count,
                sort_priority=MC_REFERENCE_DOMINANT_PRIORITY,
                status="active",
            )
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1

        # Dormant insight'lar (count == 0 olan MC'ler)
        for mc_num, count in mc_counts.items():
            if count > 0:
                continue

            title = f"MC{mc_num} hic kullanilmayan kural"
            content = (
                f"Son {MC_REFERENCE_PERIOD_DAYS} gunde MC{mc_num} kurali "
                f"hic referans verilmedi. Bu kural ya gereksiz ya da koc tarafindan "
                f"hatirlanmiyor - gozden gecirilmesi onerilir."
            )
            source_refs = {
                "period_days": MC_REFERENCE_PERIOD_DAYS,
                "total_assistant_messages": total,
                "mc_counts": mc_counts,
                "mc_number": int(mc_num),
            }

            result = _upsert_insight_absolute(
                db=db,
                user_id=user_id,
                insight_type="mc_reference_frequency",
                title=title,
                content=content,
                confidence_basis="pattern_grounded",
                source_refs=source_refs,
                evidence_count=0,
                sort_priority=1,
                status="dormant",
            )
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1

        return {
            "created": created,
            "updated": updated,
            "skipped_reason": None,
            "total_messages": total,
            "mc_counts": mc_counts,
        }

