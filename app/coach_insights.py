"""
app/coach_insights.py

Wave-2 Hafta 1 Davranissal Hafiza modulu.

Mimari (ADR-016 Saf Karma A):
- 8 deterministik extractor (ADR-001 mimarisi)
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

# kota-exempt: cron (sistem-tetikli, kullanici basina gunde bir kez) — kullanici bu yolu
#              donguye sokamaz. Kullanicinin sohbet hakkini sistem isi tuketmemeli.
#              NOT: paylasilan saglayici kotasini yine de harcar; toplam maliyet gorunurlugu
#              icin cron cagrilarinin ayri muhasebesi acik is (denetim D24 ailesi).


from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Iterator, Literal, Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

import re
from collections import Counter

from app.models import (
    CoachInsight,
    Transaction,
    TransactionType,
    ActionHistory,
    CoachMemory,
    PendingAction,
    Account,
    MasterCheckpoint,
)
from app.rules_engine import _scope  # M73: extractor'lar aktif workspace kapsamında (batch personal-scope'lar)
from app.money_format import format_para as _para  # BUG #256 (H4): para etiketi tek kaynak

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
    source_refs_json = json.dumps(source_refs, ensure_ascii=False, default=float)  # ADR-030: Decimal→float JSON sınırı

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
                # M92 (Wave-7): nullslast — SQLite NULL'ları DESC'te sona, Postgres başa koyar (dialect
                # divergence). NULL-öncelikli/tarihsiz insight'lar Postgres'te YANLIŞ olarak başa sıralanıp
                # Top-N prompt enjeksiyonunu bozardı. Açık nullslast iki dialect'i hizalar (format_insights ile tutarlı).
                CoachInsight.sort_priority.desc().nullslast(),
                CoachInsight.last_seen_at.desc().nullslast(),
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


def _sweep_insights_dormant(db: Session, user_id: int, insight_type: str,
                            active_titles_now: set) -> int:
    """
    BUG #140 fix (P1-4): Bir insight_type için ŞU AN üretilmeyen (active_titles_now dışı)
    aktif insight'ları dormant'a indirir. category_account_preference'da vardı; decision_rhythm
    ve mc_reference'da YOKTU → dominant dilim/top-3 değişince eski başlık active kalıyordu
    (kullanıcıya bayat sinyal). Yeniden-kullanılabilir sweep (DRY).
    """
    existing = (
        db.query(CoachInsight)
        .filter(
            CoachInsight.user_id == user_id,
            CoachInsight.insight_type == insight_type,
            CoachInsight.status == "active",
        )
        .all()
    )
    now = datetime.utcnow()
    swept = 0
    for ins in existing:
        if ins.title in active_titles_now:
            continue
        ins.status = "dormant"
        ins.last_seen_at = now
        ins.sort_priority = 1
        swept += 1
    if swept > 0:
        db.commit()
    return swept


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

    ADR-001 mimarisi: LLM yok, regex yok, saf SQL + istatistik.
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
            # BUG #140 (P1-4): yeterli veri var ama dominant dilim YOK → örüntü dağılmış;
            # eski aktif decision_rhythm insight'ını dormant'a indir (bayat kalmasın).
            swept = _sweep_insights_dormant(db, user_id, "decision_rhythm", set())
            log.info(
                f"no dominant slot (max ratio {dominant_ratio:.0%} < "
                f"{DECISION_RHYTHM_DOMINANT_RATIO:.0%}), dormant_swept={swept}, skipping"
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

        # BUG #140 (P1-4): dominant dilim değişmişse eski başlık(lar)ı dormant'a indir
        # (ör. "sabah" → "aksam": eski "...sabah dilminde" active kalmasın).
        swept = _sweep_insights_dormant(db, user_id, "decision_rhythm", {title})
        log.info(f"insight saved/updated: '{title}', dormant_swept={swept}")


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
    source_refs_json = json.dumps(source_refs, ensure_ascii=False, default=float)  # ADR-030: Decimal→float JSON sınırı

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
    # BUG #155 fix (P2-4/CI-004): update yolunda last_evidence_at güncellenmiyordu → yeni kanıt
    # gelse de kanıt-tazeliği bayat kalıyor, freshness sıralaması bozuluyordu. Create yoluyla
    # parite: kanıt varsa taze zaman damgası (yoksa mevcut korunur).
    if evidence_count > 0:
        existing.last_evidence_at = now
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
        active_titles_now: set = set()  # BUG #140 (P1-4): bu çalışmada aktif yapılan başlıklar

        # Dominant insight'lar (top 3, count > 0)
        for rank, (mc_num, count) in enumerate(ranked[:MC_REFERENCE_TOP_K], start=1):
            if count == 0:
                continue

            title = f"MC{mc_num} sik referans verilen kural"
            active_titles_now.add(title)
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

        # BUG #140 (P1-4): top-3 DIŞINA düşen (count>0 ama rank 4-8) eski aktif "sik referans"
        # insight'larını dormant'a indir. Eskiden yalnızca count==0 dormant'a düşüyor, top-3'ten
        # çıkan ama hâlâ count>0 olan MC'ler active kalıyordu (bayat "sık referans" sinyali).
        dormant_swept = _sweep_insights_dormant(
            db, user_id, "mc_reference_frequency", active_titles_now
        )

        return {
            "created": created,
            "updated": updated,
            "dormant_swept": dormant_swept,
            "skipped_reason": None,
            "total_messages": total,
            "mc_counts": mc_counts,
        }


# ============================================================
# EXTRACTOR 3/9: question_typology (MITI 4 / OARS)
# ============================================================
# Sektor standardi: Motivational Interviewing Treatment Integrity 4.2.1
# (Moyers et al.) - kocun MI uyumunu olcen mimari. Stanford GPTCoach
# (Jorke et al. CHI 2025) bunu LLM koclugu icin uyarladi.
#
# Olculer:
# - Open vs Closed Question orani (pct_open hedef >= %40, MITI %70)
# - Reflection-to-Question Ratio (R:Q hedef >= 0.5, MITI 1)
#   * Esikleri MITI'den dusurduk cunku Turkce + LLM baglaminda
#     baslangic seviyesi yeterli; ilerde kalibre edilir.
#
# Veri kaynagi: coach_memories role='assistant' son 30 gun.
# Tetikleme: Periyodik (lifespan startup hook + APScheduler).
# Helper: _upsert_insight_absolute (full-state UPSERT - durum
#         degisirse eski insight 'dormant'a duser).

# Open question pattern - "ne/nasil/hangi" ile baslar veya icerir
QT_OPEN_PATTERN = re.compile(
    r"\b(ne|nasil|hangi|niye|neden|nerede|nereye|nereden|kim|kac|ne kadar|"
    r"anlat|tarif et|aciklayabilir misin|ne dusunuyorsun|nelerdir)\b",
    re.IGNORECASE,
)
# Closed question - "mi/mu" partikul sorusu
QT_CLOSED_PATTERN = re.compile(
    r"\b(mi|mu|mı|mü|misin|musun|misiniz|musunuz|var mi|var mı|olur mu|"
    r"degil mi|değil mi|olmuyor mu|oldu mu|yapar misin|yapar mısın|dogru mu|doğru mu)\b\??$",
    re.IGNORECASE | re.MULTILINE,
)
# Reflection - soru degil ama anlama/yansitma cumlesi
QT_REFLECTION_PATTERN = re.compile(
    r"\b(gibi gorunuyor|gibi görünüyor|sanki|demek ki|anliyorum|anlıyorum|"
    r"hissediyorsun|hissediyorsunuz|fark ediyorum|sezdigi[mn]|sezdiğim|"
    r"yani sen|yani siz|ozetle|özetle|genel olarak)\b",
    re.IGNORECASE,
)

QT_PERIOD_DAYS = 30
QT_MIN_QUESTIONS = 30  # MITI 4 minimum bantla uyumlu
QT_PCT_OPEN_THRESHOLD = 0.40  # %40 alti = MI uyumsuz
QT_RQ_THRESHOLD = 0.50        # 0.5 alti = direktif tarz
QT_HEALTHY_PRIORITY = 5
QT_WARNING_PRIORITY = 10


def _split_into_sentences(text: str) -> list:
    """Cumle ayraci - noktalama isaretini cumlede birakir (lookbehind split).
    Boylece '?' bitisli cumleler endswith kontrolundan dogru gecer."""
    if not text:
        return []
    # Lookahead degil lookbehind: bolme noktasi noktalamadan SONRA gelir,
    # '?' cumlede kalir -> sentence.endswith("?") dogru calisiyor.
    parts = re.split(r"(?<=[.!?;])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _classify_sentence(sentence: str) -> str:
    """
    Bir cumleyi siniflandir: 'open_q', 'closed_q', 'reflection', 'other'.

    Mantik:
    - '?' ile bitiyor veya closed pattern eslesiyor -> soru
    - Open pattern oncelikli -> open_q
    - Closed pattern -> closed_q
    - Reflection pattern -> reflection
    - Hicbiri -> other
    """
    is_question = sentence.endswith("?") or QT_CLOSED_PATTERN.search(sentence)

    if is_question:
        if QT_OPEN_PATTERN.search(sentence):
            return "open_q"
        return "closed_q"

    if QT_REFLECTION_PATTERN.search(sentence):
        return "reflection"

    return "other"


def extract_question_typology(db: Session, user_id: int) -> dict:
    """
    Son 30 gun assistant mesajlarinda OARS metriklerini olcer.
    Full-state UPSERT: her insight tipi her cagrida update edilir,
    aktif kosul yoksa dormant'a duser.
    """
    with extractor_telemetry("question_typology", user_id=user_id):
        cutoff = datetime.utcnow() - timedelta(days=QT_PERIOD_DAYS)

        messages = (
            db.query(CoachMemory)
            .filter(
                CoachMemory.user_id == user_id,
                CoachMemory.role == "assistant",
                CoachMemory.timestamp >= cutoff,
            )
            .all()
        )

        open_count = 0
        closed_count = 0
        reflection_count = 0

        for msg in messages:
            for sentence in _split_into_sentences(msg.content or ""):
                cls = _classify_sentence(sentence)
                if cls == "open_q":
                    open_count += 1
                elif cls == "closed_q":
                    closed_count += 1
                elif cls == "reflection":
                    reflection_count += 1

        total_q = open_count + closed_count
        pct_open = (open_count / total_q) if total_q > 0 else 0.0
        rq_ratio = (reflection_count / total_q) if total_q > 0 else 0.0

        base_refs = {
            "period_days": QT_PERIOD_DAYS,
            "total_messages": len(messages),
            "open_count": open_count,
            "closed_count": closed_count,
            "reflection_count": reflection_count,
            "total_questions": total_q,
            "pct_open": round(pct_open, 3),
            "rq_ratio": round(rq_ratio, 3),
        }

        created = 0
        updated = 0

        # Insufficient data durumu - 4 insight'i full-state yaz
        if total_q < QT_MIN_QUESTIONS:
            for title, content, status, evidence, prio in [
                (
                    "Yetersiz veri - OARS metrikleri",
                    f"Son {QT_PERIOD_DAYS} gunde sadece {total_q} soru tespit edildi "
                    f"(min {QT_MIN_QUESTIONS}). MI uyum analizi icin yetersiz.",
                    "active", total_q, 1,
                ),
                ("Dusuk acik soru orani", "Yetersiz veri", "dormant", 0, 1),
                ("Dusuk reflection-soru orani", "Yetersiz veri", "dormant", 0, 1),
                ("OARS dengesi saglikli", "Yetersiz veri", "dormant", 0, 1),
            ]:
                r = _upsert_insight_absolute(
                    db=db, user_id=user_id,
                    insight_type="question_typology",
                    title=title, content=content,
                    confidence_basis="data_grounded",
                    source_refs=base_refs,
                    evidence_count=evidence,
                    sort_priority=prio,
                    status=status,
                )
                if r == "created":
                    created += 1
                elif r == "updated":
                    updated += 1

            return {
                "created": created, "updated": updated,
                "skipped_reason": f"insufficient_questions ({total_q} < {QT_MIN_QUESTIONS})",
                "metrics": base_refs,
            }

        # Yeterli veri - 4 insight'i full-state UPSERT
        low_open = pct_open < QT_PCT_OPEN_THRESHOLD
        low_rq = rq_ratio < QT_RQ_THRESHOLD
        healthy = (not low_open) and (not low_rq)

        insights_state = [
            (
                "Yetersiz veri - OARS metrikleri",
                "Yeterli soru tespit edildi, bu uyari aktif degil.",
                "dormant", 0, 1,
            ),
            (
                "Dusuk acik soru orani",
                f"Acik soru orani %{pct_open*100:.1f} (hedef >=%{QT_PCT_OPEN_THRESHOLD*100:.0f}). "
                f"Koc cok kapali soru soruyor, MI uyumu dusuk. "
                f"Open: {open_count}, Closed: {closed_count}.",
                "active" if low_open else "dormant",
                closed_count if low_open else 0,
                QT_WARNING_PRIORITY,
            ),
            (
                "Dusuk reflection-soru orani",
                f"R:Q orani {rq_ratio:.2f} (hedef >={QT_RQ_THRESHOLD}). "
                f"Koc cok soru soruyor, az yansitma yapiyor - direktif tarz baskin. "
                f"Reflections: {reflection_count}, Questions: {total_q}.",
                "active" if low_rq else "dormant",
                total_q if low_rq else 0,
                QT_WARNING_PRIORITY,
            ),
            (
                "OARS dengesi saglikli",
                f"MITI metrikleri yeterlilik bandinda: pct_open=%{pct_open*100:.1f}, "
                f"R:Q={rq_ratio:.2f}. Koc MI uyumlu sorular soruyor.",
                "active" if healthy else "dormant",
                total_q if healthy else 0,
                QT_HEALTHY_PRIORITY,
            ),
        ]

        for title, content, status, evidence, prio in insights_state:
            r = _upsert_insight_absolute(
                db=db, user_id=user_id,
                insight_type="question_typology",
                title=title, content=content,
                confidence_basis="data_grounded",
                source_refs=base_refs,
                evidence_count=evidence,
                sort_priority=prio,
                status=status,
            )
            if r == "created":
                created += 1
            elif r == "updated":
                updated += 1

        return {
            "created": created, "updated": updated,
            "skipped_reason": None,
            "metrics": base_refs,
        }


# ============================================================
# EXTRACTOR 4/9: category_account_preference
# ============================================================
# Sektor temeli: Mental accounting (Thaler 1985) + NBER 2023 (Agarwal et al.)
# "individuals use the same card for the same purpose" - kategori bazli hesap
# tercihi davranissal olarak olculmus istatistiki anlamli patern.
#
# Mantik: Son 90 gun expense transaction'lar, kategori-hesap esleşmesi.
# Bir kategori icin dominant hesap (count >= 5 AND share >= %70) -> active insight.
# Pattern bozulursa (yeni hesap tercihi vs) -> dormant'a duser.
#
# Veri kaynagi: transactions tablosu (transaction_type='expense', category NOT NULL,
# account_id NOT NULL).
# Tetikleme: Periyodik (lifespan startup hook + APScheduler).
# Helper: _upsert_insight_absolute + ek dormant cleanup pass.

CAP_PERIOD_DAYS = 90
CAP_MIN_TRANSACTIONS = 5      # Min anlamli sample
CAP_DOMINANT_THRESHOLD = 0.70  # %70 dominant esik
CAP_DOMINANT_PRIORITY = 8


def extract_category_account_preference(db: Session, user_id: int) -> dict:
    """
    Son 90 gun expense transaction'larinda kategori basina dominant hesabi tespit eder.
    Full-state UPSERT: her cagrida hem yeni dominant'lari yazar/gunceller, hem de
    eski dominant olup artik olmayan insight'lari dormant'a indirir.

    Donus: {"created": int, "updated": int, "dormant_swept": int,
            "dominant_count": int, "categories_analyzed": int}
    """
    with extractor_telemetry("category_account_preference", user_id=user_id):
        cutoff = datetime.utcnow() - timedelta(days=CAP_PERIOD_DAYS)

        # 1) Account isimlerini bir defa cek (label icin)
        accounts = db.query(Account).filter(_scope(Account, user_id)).all()
        account_name_map = {a.id: a.name for a in accounts}

        # 2) Son 90 gun expense + category NOT NULL + account NOT NULL
        rows = (
            db.query(Transaction.category, Transaction.account_id, func.count(Transaction.id))
            .filter(
                _scope(Transaction, user_id),  # M73 workspace-scope
                Transaction.transaction_type == TransactionType.expense,
                Transaction.category.isnot(None),
                Transaction.account_id.isnot(None),
                Transaction.transaction_date >= cutoff.date(),
            )
            .group_by(Transaction.category, Transaction.account_id)
            .all()
        )

        # 3) Kategori bazinda toplam ve hesap bazinda count cikar
        per_category: dict = {}  # category -> {account_id: count}
        for category, account_id, cnt in rows:
            per_category.setdefault(category, {})[account_id] = cnt

        created = 0
        updated = 0
        active_titles_now: set = set()

        # 4) Her kategori icin dominant hesap kontrolu
        for category, acct_counts in per_category.items():
            total = sum(acct_counts.values())
            if total < CAP_MIN_TRANSACTIONS:
                continue

            top_account_id, top_count = max(acct_counts.items(), key=lambda kv: kv[1])
            share = top_count / total

            if share < CAP_DOMINANT_THRESHOLD:
                continue

            account_label = account_name_map.get(top_account_id, f"Hesap #{top_account_id}")
            title = f"Kategori tercihi: {category}"
            content = (
                f"Son {CAP_PERIOD_DAYS} gunde '{category}' kategorisinde "
                f"{total} expense islemi yapildi, bunlarin {top_count}/{total} "
                f"({share*100:.0f}%) tanesi '{account_label}' hesabindan. "
                f"Bu kategori icin dominant odeme tercihi tespit edildi."
            )
            source_refs = {
                "period_days": CAP_PERIOD_DAYS,
                "category": category,
                "dominant_account_id": top_account_id,
                "dominant_account_name": account_label,
                "dominant_count": top_count,
                "total_transactions": total,
                "share": round(share, 3),
                "all_accounts_distribution": {
                    str(aid): cnt for aid, cnt in acct_counts.items()
                },
            }

            r = _upsert_insight_absolute(
                db=db, user_id=user_id,
                insight_type="category_account_preference",
                title=title, content=content,
                confidence_basis="data_grounded",
                source_refs=source_refs,
                evidence_count=top_count,
                sort_priority=CAP_DOMINANT_PRIORITY,
                status="active",
            )
            if r == "created":
                created += 1
            elif r == "updated":
                updated += 1

            active_titles_now.add(title)

        # 5) DORMANT SWEEP: Eski category_account_preference insight'lari arasinda
        #    su an dominant olmayanlari dormant'a indir.
        existing = (
            db.query(CoachInsight)
            .filter(
                CoachInsight.user_id == user_id,
                CoachInsight.insight_type == "category_account_preference",
                CoachInsight.status == "active",
            )
            .all()
        )

        dormant_swept = 0
        now = datetime.utcnow()
        for ins in existing:
            if ins.title in active_titles_now:
                continue
            ins.status = "dormant"
            ins.last_seen_at = now
            ins.sort_priority = 1
            dormant_swept += 1

        if dormant_swept > 0:
            db.commit()

        return {
            "created": created,
            "updated": updated,
            "dormant_swept": dormant_swept,
            "dominant_count": len(active_titles_now),
            "categories_analyzed": len(per_category),
        }


# ============================================================
# EXTRACTOR 5/9: action_rejection_pattern
# ============================================================
# Sektor temeli:
# - PITCH paper (Abbas et al. CHI 2026) - 14 gun longitudinal coaching study
#   "diverse interaction patterns: accepted / negotiated / resisted / disengaged"
# - Algorithmic aversion (Dietvorst, Simmons, Massey 2015) - kullanicilar AI
#   onerilerini sistematik olarak reddedebilir, bu davranissal sinyaldir
# - Bertrand et al. - "experts more likely to reject AI recommendations"
#
# Mantik: Son 90 gun PendingAction'lar arasinda her action_type icin
# rejection rate hesapla. >= %50 ve >= 5 resolved sample varsa active insight.
# Pending statu hesaba katilmaz (henuz karar verilmedi). Failed statu da
# hesaba katilmaz (executor hatasi, kullanici karari degil).
#
# Veri kaynagi: pending_actions tablosu (status='rejected' veya 'executed').
# Tetikleme: Periyodik (lifespan startup hook + APScheduler).
# Helper: Manuel SWEEP pass - dinamik action_type setleri.

ARP_PERIOD_DAYS = 90
ARP_MIN_RESOLVED = 5
ARP_REJECTION_THRESHOLD = 0.50
ARP_DOMINANT_PRIORITY = 9


def extract_action_rejection_pattern(db: Session, user_id: int) -> dict:
    """
    Son 90 gun pending action'larinda action_type basina rejection rate hesapla.
    >= %50 rejection AND >= 5 resolved sample -> active insight.
    Pattern bozulursa (kullanici kabul etmeye basladiysa) -> dormant.

    Donus: {"created": int, "updated": int, "dormant_swept": int,
            "active_count": int, "action_types_analyzed": int}
    """
    with extractor_telemetry("action_rejection_pattern", user_id=user_id):
        from app.models import PendingAction, ActionStatus

        cutoff = datetime.utcnow() - timedelta(days=ARP_PERIOD_DAYS)

        # 1) Action type basinda rejected ve executed sayisi
        rows = (
            db.query(
                PendingAction.action_type,
                PendingAction.status,
                func.count(PendingAction.id),
            )
            .filter(
                _scope(PendingAction, user_id),  # M73 workspace-scope
                PendingAction.created_at >= cutoff,
                PendingAction.status.in_([ActionStatus.rejected, ActionStatus.executed]),
            )
            .group_by(PendingAction.action_type, PendingAction.status)
            .all()
        )

        # 2) Action type bazinda dictionary olustur
        per_type: dict = {}  # action_type -> {"rejected": N, "executed": M}
        for action_type, status, cnt in rows:
            d = per_type.setdefault(action_type, {"rejected": 0, "executed": 0})
            if status == ActionStatus.rejected:
                d["rejected"] = cnt
            elif status == ActionStatus.executed:
                d["executed"] = cnt

        created = 0
        updated = 0
        active_titles_now: set = set()

        # 3) Her action_type icin rejection rate kontrolu
        for action_type, counts in per_type.items():
            rejected = counts["rejected"]
            executed = counts["executed"]
            total = rejected + executed

            if total < ARP_MIN_RESOLVED:
                continue

            rejection_rate = rejected / total

            if rejection_rate < ARP_REJECTION_THRESHOLD:
                continue

            title = f"Aksiyon ret pateni: {action_type}"
            content = (
                f"Son {ARP_PERIOD_DAYS} gunde '{action_type}' tipinde {total} "
                f"oneri yapildi, bunlarin {rejected}/{total} "
                f"({rejection_rate*100:.0f}%) tanesi reddedildi. "
                f"Bu action tipi icin kullanicinin red egilimi yuksek - "
                f"koc onerilerini gozden gecirmek gerekebilir."
            )
            source_refs = {
                "period_days": ARP_PERIOD_DAYS,
                "action_type": action_type,
                "rejected_count": rejected,
                "executed_count": executed,
                "total_resolved": total,
                "rejection_rate": round(rejection_rate, 3),
            }

            r = _upsert_insight_absolute(
                db=db, user_id=user_id,
                insight_type="action_rejection_pattern",
                title=title, content=content,
                confidence_basis="data_grounded",
                source_refs=source_refs,
                evidence_count=rejected,
                sort_priority=ARP_DOMINANT_PRIORITY,
                status="active",
            )
            if r == "created":
                created += 1
            elif r == "updated":
                updated += 1

            active_titles_now.add(title)

        # 4) DORMANT SWEEP: Dinamik action_type set, manuel sweep
        existing = (
            db.query(CoachInsight)
            .filter(
                CoachInsight.user_id == user_id,
                CoachInsight.insight_type == "action_rejection_pattern",
                CoachInsight.status == "active",
            )
            .all()
        )

        dormant_swept = 0
        now = datetime.utcnow()
        for ins in existing:
            if ins.title in active_titles_now:
                continue
            ins.status = "dormant"
            ins.last_seen_at = now
            ins.sort_priority = 1
            dormant_swept += 1

        if dormant_swept > 0:
            db.commit()

        return {
            "created": created,
            "updated": updated,
            "dormant_swept": dormant_swept,
            "active_count": len(active_titles_now),
            "action_types_analyzed": len(per_type),
        }


# ============================================================
# EXTRACTOR 6/9: breakthrough
# ============================================================
# Sektor temeli:
# - VEDAR (arxiv 2019) - Accountable Behavioral Change Detection
#   rolling baseline + recent window comparison patterni
# - NBER Saving Behavior (Fagereng et al.) - net saving vs capital gains ayrimi
# - Net worth growth benchmark - %5-10 yillik (aylik ~%0.4-0.8) saglikli
# - Bridgewater Decision Journal "pain + reflection = progress" patterni
#
# Mantik: Son 30 gun ortalamasi vs onceki 90 gun ortalamasi karsilastirmasi.
# 4 bilesen ayri ayri olculur:
#   1. Net worth iyilesmesi (genel)
#   2. Kart borcu azalmasi
#   3. Kredi borcu azalmasi
#   4. Yatirim buyumesi
# Her biri ayri "Kutlanacak ilerleme" insight'i - milestone celebration engine.
#
# Veri kaynagi: net_worth_snapshot tablosu.
# Tetikleme: Periyodik (lifespan startup hook + APScheduler).
# Helper: Manuel SWEEP pass.
#
# Negatif net worth durumu: yuzde mantigi kirilir (-30K'dan -28K'ya = +%6.6 mi
# yoksa +2K mi?). Bu yuzden net worth icin MUTLAK ESIK kullaniyoruz.
# Kart/kredi borcu pozitif tutuluyor (kalan borc miktari) - azalma iyilesme.

BT_RECENT_WINDOW_DAYS = 30
BT_BASELINE_WINDOW_DAYS = 90
BT_MIN_SNAPSHOTS_RECENT = 20    # 30 gunluk pencere icin min 20 snapshot
BT_MIN_SNAPSHOTS_BASELINE = 60  # 90 gunluk pencere icin min 60 snapshot
BT_NET_WORTH_THRESHOLD_TL = 5000.0  # Mutlak iyilesme esigi
BT_DEBT_REDUCTION_THRESHOLD_TL = 2000.0  # Borc azalma esigi
BT_INVESTMENT_GROWTH_THRESHOLD_TL = 3000.0  # Yatirim buyume esigi
BT_DOMINANT_PRIORITY = 7


def extract_breakthrough(db: Session, user_id: int) -> dict:
    """
    Net worth snapshot'larinda 30 gun vs 90 gun karsilastirmasi yaparak
    finansal iyilesme sinyallerini insight olarak yazar.

    Donus: {"created": int, "updated": int, "dormant_swept": int,
            "active_count": int, "skipped_reason": str | None}
    """
    with extractor_telemetry("breakthrough", user_id=user_id):
        from app.models import NetWorthSnapshot

        now = datetime.utcnow()
        recent_cutoff = (now - timedelta(days=BT_RECENT_WINDOW_DAYS)).date()
        baseline_cutoff = (now - timedelta(days=BT_RECENT_WINDOW_DAYS + BT_BASELINE_WINDOW_DAYS)).date()

        recent_snaps = (
            db.query(NetWorthSnapshot)
            .filter(
                _scope(NetWorthSnapshot, user_id),  # M73 workspace-scope
                NetWorthSnapshot.snapshot_date >= recent_cutoff,
            )
            .all()
        )
        baseline_snaps = (
            db.query(NetWorthSnapshot)
            .filter(
                _scope(NetWorthSnapshot, user_id),  # M73 workspace-scope
                NetWorthSnapshot.snapshot_date >= baseline_cutoff,
                NetWorthSnapshot.snapshot_date < recent_cutoff,
            )
            .all()
        )

        if len(recent_snaps) < BT_MIN_SNAPSHOTS_RECENT or len(baseline_snaps) < BT_MIN_SNAPSHOTS_BASELINE:
            existing = (
                db.query(CoachInsight)
                .filter(
                    CoachInsight.user_id == user_id,
                    CoachInsight.insight_type == "breakthrough",
                    CoachInsight.status == "active",
                )
                .all()
            )
            for ins in existing:
                ins.status = "dormant"
                ins.last_seen_at = now
                ins.sort_priority = 1
            if existing:
                db.commit()

            return {
                "created": 0, "updated": 0,
                "dormant_swept": len(existing),
                "active_count": 0,
                "skipped_reason": (
                    f"insufficient_snapshots "
                    f"(recent={len(recent_snaps)}<{BT_MIN_SNAPSHOTS_RECENT} or "
                    f"baseline={len(baseline_snaps)}<{BT_MIN_SNAPSHOTS_BASELINE})"
                ),
            }

        def avg(snaps, attr):
            vals = [getattr(s, attr) or 0.0 for s in snaps]
            return sum(vals) / len(vals) if vals else 0.0

        metrics = {
            "net_worth_full": (avg(recent_snaps, "net_worth_full"), avg(baseline_snaps, "net_worth_full")),
            "card_debt": (avg(recent_snaps, "card_debt"), avg(baseline_snaps, "card_debt")),
            "loan_debt": (avg(recent_snaps, "loan_debt"), avg(baseline_snaps, "loan_debt")),
            "investment_value": (avg(recent_snaps, "investment_value"), avg(baseline_snaps, "investment_value")),
        }

        breakthroughs = []

        # Net worth iyilesmesi
        nw_recent, nw_base = metrics["net_worth_full"]
        nw_delta = nw_recent - nw_base
        if nw_delta >= BT_NET_WORTH_THRESHOLD_TL:
            breakthroughs.append((
                "Kutlanacak ilerleme: Net deger iyilesmesi",
                f"Son {BT_RECENT_WINDOW_DAYS} gun ortalama net deger {_para(nw_recent, ondalik=0)}, "
                f"onceki {BT_BASELINE_WINDOW_DAYS} gun ortalamasi {_para(nw_base, ondalik=0)} idi. "
                f"Net iyilesme: +{_para(nw_delta, ondalik=0)}. Bu finansal durumda anlamli bir ilerleme.",
                {
                    "component": "net_worth_full",
                    "recent_avg": round(nw_recent, 2),
                    "baseline_avg": round(nw_base, 2),
                    "delta": round(nw_delta, 2),
                    "threshold": BT_NET_WORTH_THRESHOLD_TL,
                    "recent_window_days": BT_RECENT_WINDOW_DAYS,
                    "baseline_window_days": BT_BASELINE_WINDOW_DAYS,
                },
                int(nw_delta / 1000),
            ))

        # Kart borcu azalmasi
        cd_recent, cd_base = metrics["card_debt"]
        cd_delta = cd_base - cd_recent  # azalma pozitif
        if cd_delta >= BT_DEBT_REDUCTION_THRESHOLD_TL:
            breakthroughs.append((
                "Kutlanacak ilerleme: Kart borcu azalmasi",
                f"Son {BT_RECENT_WINDOW_DAYS} gun ortalama kart borcu {_para(cd_recent, ondalik=0)}, "
                f"onceki {BT_BASELINE_WINDOW_DAYS} gun ortalamasi {_para(cd_base, ondalik=0)} idi. "
                f"Azalma: -{_para(cd_delta, ondalik=0)}. Borc disiplini calisiyor.",
                {
                    "component": "card_debt",
                    "recent_avg": round(cd_recent, 2),
                    "baseline_avg": round(cd_base, 2),
                    "delta_reduction": round(cd_delta, 2),
                    "threshold": BT_DEBT_REDUCTION_THRESHOLD_TL,
                    "recent_window_days": BT_RECENT_WINDOW_DAYS,
                    "baseline_window_days": BT_BASELINE_WINDOW_DAYS,
                },
                int(cd_delta / 1000),
            ))

        # Kredi borcu azalmasi
        ld_recent, ld_base = metrics["loan_debt"]
        ld_delta = ld_base - ld_recent
        if ld_delta >= BT_DEBT_REDUCTION_THRESHOLD_TL:
            breakthroughs.append((
                "Kutlanacak ilerleme: Kredi borcu azalmasi",
                f"Son {BT_RECENT_WINDOW_DAYS} gun ortalama kredi borcu {_para(ld_recent, ondalik=0)}, "
                f"onceki {BT_BASELINE_WINDOW_DAYS} gun ortalamasi {_para(ld_base, ondalik=0)} idi. "
                f"Azalma: -{_para(ld_delta, ondalik=0)}. Kredi odemeleri ilerliyor.",
                {
                    "component": "loan_debt",
                    "recent_avg": round(ld_recent, 2),
                    "baseline_avg": round(ld_base, 2),
                    "delta_reduction": round(ld_delta, 2),
                    "threshold": BT_DEBT_REDUCTION_THRESHOLD_TL,
                    "recent_window_days": BT_RECENT_WINDOW_DAYS,
                    "baseline_window_days": BT_BASELINE_WINDOW_DAYS,
                },
                int(ld_delta / 1000),
            ))

        # Yatirim buyumesi
        iv_recent, iv_base = metrics["investment_value"]
        iv_delta = iv_recent - iv_base
        if iv_delta >= BT_INVESTMENT_GROWTH_THRESHOLD_TL:
            breakthroughs.append((
                "Kutlanacak ilerleme: Yatirim buyumesi",
                f"Son {BT_RECENT_WINDOW_DAYS} gun ortalama yatirim degeri {_para(iv_recent, ondalik=0)}, "
                f"onceki {BT_BASELINE_WINDOW_DAYS} gun ortalamasi {_para(iv_base, ondalik=0)} idi. "
                f"Buyume: +{_para(iv_delta, ondalik=0)}.",
                {
                    "component": "investment_value",
                    "recent_avg": round(iv_recent, 2),
                    "baseline_avg": round(iv_base, 2),
                    "delta_growth": round(iv_delta, 2),
                    "threshold": BT_INVESTMENT_GROWTH_THRESHOLD_TL,
                    "recent_window_days": BT_RECENT_WINDOW_DAYS,
                    "baseline_window_days": BT_BASELINE_WINDOW_DAYS,
                },
                int(iv_delta / 1000),
            ))

        created = 0
        updated = 0
        active_titles_now: set = set()

        for title, content, refs, evidence in breakthroughs:
            r = _upsert_insight_absolute(
                db=db, user_id=user_id,
                insight_type="breakthrough",
                title=title, content=content,
                confidence_basis="data_grounded",
                source_refs=refs,
                evidence_count=max(1, evidence),
                sort_priority=BT_DOMINANT_PRIORITY,
                status="active",
            )
            if r == "created":
                created += 1
            elif r == "updated":
                updated += 1
            active_titles_now.add(title)

        # DORMANT SWEEP
        existing = (
            db.query(CoachInsight)
            .filter(
                CoachInsight.user_id == user_id,
                CoachInsight.insight_type == "breakthrough",
                CoachInsight.status == "active",
            )
            .all()
        )

        dormant_swept = 0
        for ins in existing:
            if ins.title in active_titles_now:
                continue
            ins.status = "dormant"
            ins.last_seen_at = now
            ins.sort_priority = 1
            dormant_swept += 1

        if dormant_swept > 0:
            db.commit()

        return {
            "created": created,
            "updated": updated,
            "dormant_swept": dormant_swept,
            "active_count": len(active_titles_now),
            "skipped_reason": None,
        }


# ============================================================
# EXTRACTOR 7/9: setback
# ============================================================
# Sektor temeli:
# - Loss Aversion (Tversky & Kahneman 1979) - kayiplar 2x agirlikli, esikleri
#   breakthrough'tan daha siki tutuyoruz (~%50 daha hassas)
# - Loss Aversion Online (arxiv 2601.14423, 2026) - crash duygusal tepki boom'dan
#   daha guclu, false positive psikolojik zarar verir, kalibrasyon onemli
# - FPA Behavioral Coaching (Kay) - "thoughtful framing activates loss aversion
#   to move clients forward" - setback'i panik degil eylem motivasyonu olarak kur
# - Risk Aversion design pattern - "fear-based marketing alienates users"
#   insight content'i veri+oneri, dilekce degil
#
# Mantik: breakthrough'un ayna goruntusu - ayni altyapi, ters yon.
#   1. Net worth kotulesmesi (-3K esik, breakthrough'tan %40 hassas)
#   2. Kart borcu artisi (+1.5K esik)
#   3. Kredi borcu artisi (+1.5K esik)
#   4. Yatirim degeri kaybi (-2.5K esik)
# YENI: Birden cok kotulesme bilesimi compound signal - sort_priority 9 (yuksek)
#       tek bilesen - sort_priority 7 (orta)
#
# Veri kaynagi: net_worth_snapshot tablosu.
# Tetikleme: Periyodik (lifespan startup hook + APScheduler).
# Helper: Manuel SWEEP pass.

ST_RECENT_WINDOW_DAYS = 30
ST_BASELINE_WINDOW_DAYS = 90
ST_MIN_SNAPSHOTS_RECENT = 20
ST_MIN_SNAPSHOTS_BASELINE = 60
ST_NET_WORTH_THRESHOLD_TL = 3000.0     # Breakthrough'un %60'i (loss aversion)
ST_DEBT_INCREASE_THRESHOLD_TL = 1500.0
ST_INVESTMENT_LOSS_THRESHOLD_TL = 2500.0
ST_COMPOUND_PRIORITY = 9   # Birden fazla bilesen kotulesti
ST_DOMINANT_PRIORITY = 7   # Tek bilesen kotulesti


def extract_setback(db: Session, user_id: int) -> dict:
    """
    Net worth snapshot'larinda 30 gun vs 90 gun karsilastirmasi yaparak
    finansal kotulesme sinyallerini insight olarak yazar (setback).

    Donus: {"created": int, "updated": int, "dormant_swept": int,
            "active_count": int, "compound_setback": bool, "skipped_reason": str | None}
    """
    with extractor_telemetry("setback", user_id=user_id):
        from app.models import NetWorthSnapshot

        now = datetime.utcnow()
        recent_cutoff = (now - timedelta(days=ST_RECENT_WINDOW_DAYS)).date()
        baseline_cutoff = (now - timedelta(days=ST_RECENT_WINDOW_DAYS + ST_BASELINE_WINDOW_DAYS)).date()

        recent_snaps = (
            db.query(NetWorthSnapshot)
            .filter(
                _scope(NetWorthSnapshot, user_id),  # M73 workspace-scope
                NetWorthSnapshot.snapshot_date >= recent_cutoff,
            )
            .all()
        )
        baseline_snaps = (
            db.query(NetWorthSnapshot)
            .filter(
                _scope(NetWorthSnapshot, user_id),  # M73 workspace-scope
                NetWorthSnapshot.snapshot_date >= baseline_cutoff,
                NetWorthSnapshot.snapshot_date < recent_cutoff,
            )
            .all()
        )

        if len(recent_snaps) < ST_MIN_SNAPSHOTS_RECENT or len(baseline_snaps) < ST_MIN_SNAPSHOTS_BASELINE:
            existing = (
                db.query(CoachInsight)
                .filter(
                    CoachInsight.user_id == user_id,
                    CoachInsight.insight_type == "setback",
                    CoachInsight.status == "active",
                )
                .all()
            )
            for ins in existing:
                ins.status = "dormant"
                ins.last_seen_at = now
                ins.sort_priority = 1
            if existing:
                db.commit()

            return {
                "created": 0, "updated": 0,
                "dormant_swept": len(existing),
                "active_count": 0,
                "compound_setback": False,
                "skipped_reason": (
                    f"insufficient_snapshots "
                    f"(recent={len(recent_snaps)}<{ST_MIN_SNAPSHOTS_RECENT} or "
                    f"baseline={len(baseline_snaps)}<{ST_MIN_SNAPSHOTS_BASELINE})"
                ),
            }

        def avg(snaps, attr):
            vals = [getattr(s, attr) or 0.0 for s in snaps]
            return sum(vals) / len(vals) if vals else 0.0

        metrics = {
            "net_worth_full": (avg(recent_snaps, "net_worth_full"), avg(baseline_snaps, "net_worth_full")),
            "card_debt": (avg(recent_snaps, "card_debt"), avg(baseline_snaps, "card_debt")),
            "loan_debt": (avg(recent_snaps, "loan_debt"), avg(baseline_snaps, "loan_debt")),
            "investment_value": (avg(recent_snaps, "investment_value"), avg(baseline_snaps, "investment_value")),
        }

        setbacks = []

        # Net worth kotulesmesi
        nw_recent, nw_base = metrics["net_worth_full"]
        nw_drop = nw_base - nw_recent
        if nw_drop >= ST_NET_WORTH_THRESHOLD_TL:
            setbacks.append((
                "Dikkat: Net deger kotulesmesi",
                f"Son {ST_RECENT_WINDOW_DAYS} gun ortalama net deger {_para(nw_recent, ondalik=0)}, "
                f"onceki {ST_BASELINE_WINDOW_DAYS} gun ortalamasi {_para(nw_base, ondalik=0)} idi. "
                f"Dusus: -{_para(nw_drop, ondalik=0)}. Harcama-gelir dengesi gozden gecirilmeli.",
                {
                    "component": "net_worth_full",
                    "recent_avg": round(nw_recent, 2),
                    "baseline_avg": round(nw_base, 2),
                    "drop": round(nw_drop, 2),
                    "threshold": ST_NET_WORTH_THRESHOLD_TL,
                    "recent_window_days": ST_RECENT_WINDOW_DAYS,
                    "baseline_window_days": ST_BASELINE_WINDOW_DAYS,
                },
                int(nw_drop / 1000),
            ))

        # Kart borcu artisi
        cd_recent, cd_base = metrics["card_debt"]
        cd_increase = cd_recent - cd_base
        if cd_increase >= ST_DEBT_INCREASE_THRESHOLD_TL:
            setbacks.append((
                "Dikkat: Kart borcu artisi",
                f"Son {ST_RECENT_WINDOW_DAYS} gun ortalama kart borcu {_para(cd_recent, ondalik=0)}, "
                f"onceki {ST_BASELINE_WINDOW_DAYS} gun ortalamasi {_para(cd_base, ondalik=0)} idi. "
                f"Artis: +{_para(cd_increase, ondalik=0)}. Kart kullanim disiplini onerilir.",
                {
                    "component": "card_debt",
                    "recent_avg": round(cd_recent, 2),
                    "baseline_avg": round(cd_base, 2),
                    "increase": round(cd_increase, 2),
                    "threshold": ST_DEBT_INCREASE_THRESHOLD_TL,
                    "recent_window_days": ST_RECENT_WINDOW_DAYS,
                    "baseline_window_days": ST_BASELINE_WINDOW_DAYS,
                },
                int(cd_increase / 1000),
            ))

        # Kredi borcu artisi
        ld_recent, ld_base = metrics["loan_debt"]
        ld_increase = ld_recent - ld_base
        if ld_increase >= ST_DEBT_INCREASE_THRESHOLD_TL:
            setbacks.append((
                "Dikkat: Kredi borcu artisi",
                f"Son {ST_RECENT_WINDOW_DAYS} gun ortalama kredi borcu {_para(ld_recent, ondalik=0)}, "
                f"onceki {ST_BASELINE_WINDOW_DAYS} gun ortalamasi {_para(ld_base, ondalik=0)} idi. "
                f"Artis: +{_para(ld_increase, ondalik=0)}. Yeni kredi/refinansman kararlari gozden gecirilmeli.",
                {
                    "component": "loan_debt",
                    "recent_avg": round(ld_recent, 2),
                    "baseline_avg": round(ld_base, 2),
                    "increase": round(ld_increase, 2),
                    "threshold": ST_DEBT_INCREASE_THRESHOLD_TL,
                    "recent_window_days": ST_RECENT_WINDOW_DAYS,
                    "baseline_window_days": ST_BASELINE_WINDOW_DAYS,
                },
                int(ld_increase / 1000),
            ))

        # Yatirim kaybi
        iv_recent, iv_base = metrics["investment_value"]
        iv_loss = iv_base - iv_recent
        if iv_loss >= ST_INVESTMENT_LOSS_THRESHOLD_TL:
            setbacks.append((
                "Dikkat: Yatirim deger kaybi",
                f"Son {ST_RECENT_WINDOW_DAYS} gun ortalama yatirim degeri {_para(iv_recent, ondalik=0)}, "
                f"onceki {ST_BASELINE_WINDOW_DAYS} gun ortalamasi {_para(iv_base, ondalik=0)} idi. "
                f"Kayip: -{_para(iv_loss, ondalik=0)}. Piyasa hareketi mi davranissal mi - ayrimi onemli.",
                {
                    "component": "investment_value",
                    "recent_avg": round(iv_recent, 2),
                    "baseline_avg": round(iv_base, 2),
                    "loss": round(iv_loss, 2),
                    "threshold": ST_INVESTMENT_LOSS_THRESHOLD_TL,
                    "recent_window_days": ST_RECENT_WINDOW_DAYS,
                    "baseline_window_days": ST_BASELINE_WINDOW_DAYS,
                },
                int(iv_loss / 1000),
            ))

        is_compound = len(setbacks) >= 2
        priority = ST_COMPOUND_PRIORITY if is_compound else ST_DOMINANT_PRIORITY

        created = 0
        updated = 0
        active_titles_now: set = set()

        for title, content, refs, evidence in setbacks:
            if is_compound:
                content += f" [Compound setback: {len(setbacks)} bilesen es zamanli kotulesti]"
                refs["compound_setback"] = True
                refs["compound_components"] = len(setbacks)

            r = _upsert_insight_absolute(
                db=db, user_id=user_id,
                insight_type="setback",
                title=title, content=content,
                confidence_basis="data_grounded",
                source_refs=refs,
                evidence_count=max(1, evidence),
                sort_priority=priority,
                status="active",
            )
            if r == "created":
                created += 1
            elif r == "updated":
                updated += 1
            active_titles_now.add(title)

        # DORMANT SWEEP
        existing = (
            db.query(CoachInsight)
            .filter(
                CoachInsight.user_id == user_id,
                CoachInsight.insight_type == "setback",
                CoachInsight.status == "active",
            )
            .all()
        )

        dormant_swept = 0
        for ins in existing:
            if ins.title in active_titles_now:
                continue
            ins.status = "dormant"
            ins.last_seen_at = now
            ins.sort_priority = 1
            dormant_swept += 1

        if dormant_swept > 0:
            db.commit()

        return {
            "created": created,
            "updated": updated,
            "dormant_swept": dormant_swept,
            "active_count": len(active_titles_now),
            "compound_setback": is_compound,
            "skipped_reason": None,
        }


# ============================================================
# EXTRACTOR 8/9: explicit_red_line K1 (Honcho Dream Layer 1)
# ============================================================
# Sektor temeli:
# - Honcho Dream paterni (Plan v3 H1G1 karari) - iki katmanli kirmizi cizgi
#   tespiti. K1 = anlik regex, K2 = gece batch LLM consolidation.
# - Mem0 fact-extraction limitations (Atlan benchmarks) - implicit preference
#   detection %30-45, K1 sadece EXPLICIT statement'a bakar.
# - Turkish negative concord (Springer Linguistic Theory 2022) - Turkce strict
#   NC dili. "asla", "hic", "kesinlikle" + olumsuz fiil mutlak red ifadesi.
#
# Mantik: coach_memories role='user' son 90 gun mesajlari taranir, NET kirmizi
# cizgi ifadeleri regex ile yakalanir. Her tespit insight olarak yazilir.
# Aynı message_id 2 kez sayilmaz (deduplication source_refs uzerinden).
#
# Sektor felsefesi: K1 SADECE EXPLICIT statement'lari yakalar, implicit
# preference yok. False positive %0 olmasi sart - bu sebeple cok spesifik
# regex'ler. Belirsiz ifadeler ("istemem aslinda", "olur mu acaba") K2'ye
# birakilir (LLM nuance anlar).
#
# Veri kaynagi: coach_memories tablosu (role='user').
# Tetikleme: Periyodik (lifespan startup hook) - olay-tetikli de calisabilir
#           coach.py icinde mesaj kaydedildikten sonra cagirilir.
# Helper: _save_or_update_insight (Wave-1 incremental helper).
# Confidence: 'data_grounded' - kullanicinin kendi sozu, ham veri.

# Turkce explicit red line regex desenleri - 5 kategori
ERL_PATTERNS = [
    # 1. Mutlak red: "asla X'mam"
    {
        "category": "mutlak_red",
        "pattern": re.compile(
            r"\basla\s+(?:[a-zçğıöşüA-ZÇĞIİÖŞÜ\s]{1,40}?)(?:mam|mem|mayacagim|meyecegim|mayacağım|meyeceğim|maz|mez)\b",
            re.IGNORECASE | re.UNICODE,
        ),
    },
    # 2. Niyet beyani: "X istemiyorum / istemem"
    {
        "category": "niyet_beyani",
        "pattern": re.compile(
            r"\b(?:[a-zçğıöşüA-ZÇĞIİÖŞÜ\s]{2,50}?)\s+(?:istemiyorum|istemem|istemiyrum)\b",
            re.IGNORECASE | re.UNICODE,
        ),
    },
    # 3. Vaat: "bir daha X cekmem/almam/yapmam/acmam/kapatmam"
    {
        "category": "vaat",
        "pattern": re.compile(
            r"\bbir\s+daha\s+(?:[a-zçğıöşüA-ZÇĞIİÖŞÜ\s]{1,40}?)\s+(?:çekmem|cekmem|almam|yapmam|açmam|acmam|kapatmam|odemem|ödemem|harcamam)\b",
            re.IGNORECASE | re.UNICODE,
        ),
    },
    # 4. Kesin reddetme: "kesinlikle X-maz/mez/mam/mem"
    {
        "category": "kesin_red",
        "pattern": re.compile(
            r"\bkesinlikle\s+(?:[a-zçğıöşüA-ZÇĞIİÖŞÜ\s]{1,40}?)(?:maz|mez|mam|mem|miyorum|miyrum)\b",
            re.IGNORECASE | re.UNICODE,
        ),
    },
    # 5. Acik sinir: "kirmizi cizgi(m)"
    {
        "category": "acik_sinir",
        "pattern": re.compile(
            r"\bkırmızı\s+çizgi(?:m|mdir)?\b|\bkirmizi\s+cizgi(?:m|mdir)?\b",
            re.IGNORECASE | re.UNICODE,
        ),
    },
]

ERL_PERIOD_DAYS = 90
ERL_MAX_MESSAGE_LEN = 200      # Cok uzun mesajlar K2'ye birakilir
ERL_DOMINANT_PRIORITY = 15     # EN YUKSEK - kirmizi cizgi en kritik sinyal

# BUG #139 fix (P1-5): mutlak_red/niyet_beyani/kesin_red desenleri finansal alanla
# ANCHOR'LI DEGILDI → "asla o filmi izlemem" gibi finans-disi cumleler de kirmizi-cizgi
# insight'ina donusuyordu ("%0 false positive" iddiasiyla celisik). Bu kategoriler icin
# icerikte finansal baglam ANAHTAR KELIMESI zorunlu. (vaat = finansal fiil zaten; acik_sinir
# = kullanici acikca "kirmizi cizgi" diyor → anchor gerekmez.)
ERL_FINANCIAL_RE = re.compile(
    r"\b(?:para|nakit|kart|kredi|borç|borc|harca|harcama|tl|lira|taksit|faiz|kumar|bahis|"
    r"yatırım|yatirim|fon|hesap|öde|ode|tasarruf|bütçe|butce|kripto|hisse|altın|altin|"
    r"döviz|doviz|limit|maaş|maas|fatura|abonelik|zarf)\w*\b",
    re.IGNORECASE | re.UNICODE,
)
ERL_ANCHOR_REQUIRED = {"mutlak_red", "niyet_beyani", "kesin_red"}


def _erl_extract_match_text(match, full_text: str, max_len: int = 80) -> str:
    """Match etrafindaki kisa baglami cikar (insight title icin)."""
    start = max(0, match.start() - 10)
    end = min(len(full_text), match.end() + 20)
    excerpt = full_text[start:end].strip()
    if len(excerpt) > max_len:
        excerpt = excerpt[:max_len].rstrip() + "..."
    return excerpt


def _erl_already_processed(memory_id: int, source_refs_json: str | None) -> bool:
    """Bu memory_id daha once islenmis mi (deduplication)."""
    if not source_refs_json:
        return False
    try:
        refs = json.loads(source_refs_json)
        if isinstance(refs, list):
            return f"coach_memory:{memory_id}" in refs
        return False
    except (json.JSONDecodeError, TypeError):
        return False


def extract_explicit_red_line_k1(db: Session, user_id: int) -> dict:
    """
    Son 90 gun user mesajlarinda explicit kirmizi cizgi ifadelerini regex ile yakala.
    Honcho Dream Layer 1 - %0 false positive hedefli, sadece NET ifadeler.

    Donus: {"matched_messages": int, "new_insights": int, "updated_insights": int,
            "skipped_dedup": int, "scanned_messages": int}
    """
    with extractor_telemetry("explicit_red_line_k1", user_id=user_id):
        cutoff = datetime.utcnow() - timedelta(days=ERL_PERIOD_DAYS)

        messages = (
            db.query(CoachMemory)
            .filter(
                CoachMemory.user_id == user_id,
                CoachMemory.role == "user",
                CoachMemory.timestamp >= cutoff,
            )
            .order_by(CoachMemory.timestamp.asc())
            .all()
        )

        existing_insights = (
            db.query(CoachInsight)
            .filter(
                CoachInsight.user_id == user_id,
                CoachInsight.insight_type == "explicit_red_line",
            )
            .all()
        )
        existing_refs_map = {ins.title: ins.source_refs for ins in existing_insights}
        existing_titles = {ins.title for ins in existing_insights}

        matched_messages = 0
        new_insights = 0
        updated_insights = 0
        skipped_dedup = 0
        seen_titles_this_run: set = set()

        for msg in messages:
            content = (msg.content or "").strip()
            if not content or len(content) > ERL_MAX_MESSAGE_LEN:
                continue
            if content.endswith("?"):
                continue

            msg_matched = False

            for pat_def in ERL_PATTERNS:
                category = pat_def["category"]
                pattern = pat_def["pattern"]

                match = pattern.search(content)
                if not match:
                    continue

                # BUG #139 (P1-5): anchor gerektiren kategorilerde finansal baglam yoksa ATLA
                # ("asla o filmi izlemem" → kirmizi cizgi DEGIL; "asla kredi cekmem" → EVET).
                if category in ERL_ANCHOR_REQUIRED and not ERL_FINANCIAL_RE.search(content):
                    continue

                excerpt = _erl_extract_match_text(match, content)
                title = f"Kirmizi cizgi [{category}]: {excerpt}"
                if len(title) > 200:
                    title = title[:197] + "..."

                existing_refs_json = existing_refs_map.get(title)
                if _erl_already_processed(msg.id, existing_refs_json):
                    skipped_dedup += 1
                    continue

                if existing_refs_json:
                    try:
                        refs_list = json.loads(existing_refs_json)
                        if not isinstance(refs_list, list):
                            refs_list = []
                    except (json.JSONDecodeError, TypeError):
                        refs_list = []
                else:
                    refs_list = []

                refs_list.append(f"coach_memory:{msg.id}")
                if len(refs_list) > 50:
                    refs_list = refs_list[-50:]

                content_text = (
                    f"Kullanici acikca '{category}' kategorisinde bir kirmizi cizgi "
                    f"ifade etti. Tetikleyici metin: \"{excerpt}\". Bu ifade kullanicinin "
                    f"kendi sozune dayanir, kanit dogrudan."
                )

                _save_or_update_insight(
                    db=db,
                    user_id=user_id,
                    insight_type="explicit_red_line",
                    title=title,
                    content=content_text,
                    confidence_basis="data_grounded",
                    source_refs=refs_list,
                    is_supporting_evidence=True,
                    para_category="area",
                    priority=ERL_DOMINANT_PRIORITY,
                )

                existing_refs_map[title] = json.dumps(refs_list, default=float)  # ADR-030: Decimal→float

                if title not in seen_titles_this_run:
                    seen_titles_this_run.add(title)
                    if title in existing_titles:
                        updated_insights += 1
                    else:
                        new_insights += 1
                        existing_titles.add(title)

                msg_matched = True

            if msg_matched:
                matched_messages += 1

        return {
            "matched_messages": matched_messages,
            "new_insights": new_insights,
            "updated_insights": updated_insights,
            "skipped_dedup": skipped_dedup,
            "scanned_messages": len(messages),
        }


# ============================================================
# EXTRACTOR 9/9: explicit_red_line K2 (Honcho Dream Layer 2 - LLM)
# ============================================================
# Sektor temeli (Plan v3 H1G1 karari):
# - Honcho Dream paterni - K1 (regex %0 false positive) + K2 (LLM nuance)
# - Mem0 fact-extraction implicit preference %30-45 vs Honcho %77-90 - LLM
#   nuance gerektiren ima edilen patern tespiti icin sart
# - ADR-001 mimarisi - LLM uretici, sistem tuketici. Pydantic-benzeri schema
#   validation cikti dogrulamasi yapar, false output reddedilir.
#
# Kritik tasarim kisitlari (sema kesfi 10 May 2026):
# - FallbackProvider structured JSON output desteklemiyor
# - Tool-call trick MALFORMED_FUNCTION_CALL riski (Groq/Gemini)
# - Cozum: markdown code fence JSON + esnek manuel parse + Pydantic-style validation
#
# Mantik: K1 insight'larini topla, LLM'e batch gonder, ima edilen kirmizi
# cizgi paternleri cikar, JSON parse, insight olarak yaz (pattern_grounded).
# K1 yoksa erken cik (gereksiz LLM cagirisi yapma).
#
# Veri kaynagi: CoachInsight (insight_type='explicit_red_line', K1 yazimlari).
# Tetikleme: Periyodik gece batch (APScheduler 03:00 Istanbul) - Plan v3 D Hibrit.
# Helper: _save_or_update_insight (Wave-1 incremental, K1 ile ayni tip).
# Confidence: 'pattern_grounded' (K1 farki: K1=data_grounded direkt soz, K2=LLM cikarim).

ERL_K2_LOOKBACK_HOURS = 24
ERL_K2_MIN_K1_INSIGHTS = 1  # En az 1 K1 insight olmali (LLM'e besleme)
ERL_K2_PRIORITY = 12          # K1=15'ten az, pattern_grounded zayif kanit
ERL_K2_LLM_TIMEOUT_SEC = 60
ERL_K2_PROMPT_VERSION = "v1"

ERL_K2_SYSTEM_PROMPT = """Sen FinancialOS'un davranissal hafiza analiz motorusun.
Kullanicinin ACIK kirmizi cizgi ifadelerine bakarak IMA EDILEN (implicit) bir
kirmizi cizgi paterni cikarmaya calisiyorsun.

KURALLAR:
1. SADECE veride olan paterni yakala. Kullanicinin SOYLEMEDIGI seyi UYDURMA.
2. Tek bir explicit ifadeden patern cikarma - en az 2 farkli ifade ayni yonu gostermeli.
3. Belirsiz/yetersiz veri varsa "patterns": [] dondur. Hayalden patern uretme.
4. Anti-sycophancy: "kullanici kararliydi" gibi yorumdan kacin, sadece veriyi raporla.

CIKTI FORMATI: SADECE asagidaki JSON, kod blok icinde, hicbir ek metin yok:

```json
{
  "patterns": [
    {
      "category": "kisa_snake_case_isim",
      "description": "1-2 cumle Turkce aciklama",
      "evidence_quotes": ["alintilanan ifade 1", "alintilanan ifade 2"],
      "confidence": "medium"
    }
  ],
  "reasoning": "neden bu paterni cikardin, kisa"
}
```

confidence DEGERLERI: "medium" veya "high". "low" YASAK - implicit en az medium.
Hicbir patern bulamazsan: {"patterns": [], "reasoning": "yetersiz veri"}.
"""


def _erl_k2_parse_llm_json(text: str) -> dict | None:
    """LLM cevabindan markdown code fence icindeki JSON'i cikar ve parse et.
    Pydantic-style validation ile false output reddet."""
    if not text:
        return None

    # 1) Markdown code fence icinden JSON cikar
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        json_str = fence_match.group(1)
    else:
        # Fallback: ilk { ile son } arasini al
        first = text.find("{")
        last = text.rfind("}")
        if first == -1 or last == -1 or last <= first:
            return None
        json_str = text[first:last+1]

    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None

    # 2) Manuel schema validation
    if not isinstance(data, dict):
        return None
    if "patterns" not in data or not isinstance(data["patterns"], list):
        return None

    valid_patterns = []
    for p in data["patterns"]:
        if not isinstance(p, dict):
            continue
        category = p.get("category")
        description = p.get("description")
        evidence = p.get("evidence_quotes")
        confidence = p.get("confidence")

        if not isinstance(category, str) or not category.strip():
            continue
        if not isinstance(description, str) or not description.strip():
            continue
        if not isinstance(evidence, list) or len(evidence) < 1:
            continue
        if confidence not in ("medium", "high"):
            continue

        evidence_clean = [e for e in evidence if isinstance(e, str) and e.strip()]
        if not evidence_clean:
            continue

        valid_patterns.append({
            "category": category.strip()[:50],
            "description": description.strip()[:300],
            "evidence_quotes": evidence_clean[:5],
            "confidence": confidence,
        })

    return {
        "patterns": valid_patterns,
        "reasoning": str(data.get("reasoning", ""))[:500],
    }


def extract_explicit_red_line_k2(
    db: Session,
    user_id: int,
    provider=None,  # None ise build_provider() cagirilir; test fixture mock gecer
) -> dict:
    """
    Honcho Dream Layer 2: K1'in yazdigi explicit_red_line insight'lari
    LLM'e gonder, ima edilen patern cikarmaya calis, insight olarak yaz.

    Donus: {"k1_insights_fed": int, "patterns_detected": int, "new_insights": int,
            "skipped_reason": str | None, "batch_run_id": str}
    """
    with extractor_telemetry("explicit_red_line_k2", user_id=user_id):
        batch_run_id = f"k2_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # 1) K1 insight'larini topla (active, son 24 saat icinde olusmus/guncellenmis)
        cutoff = datetime.utcnow() - timedelta(hours=ERL_K2_LOOKBACK_HOURS)
        k1_insights = (
            db.query(CoachInsight)
            .filter(
                CoachInsight.user_id == user_id,
                CoachInsight.insight_type == "explicit_red_line",
                CoachInsight.confidence_basis == "data_grounded",  # K1 yazimi
                CoachInsight.status == "active",
                or_(
                    CoachInsight.last_seen_at >= cutoff,
                    CoachInsight.activated_at >= cutoff,
                ),
            )
            .all()
        )

        if len(k1_insights) < ERL_K2_MIN_K1_INSIGHTS:
            return {
                "k1_insights_fed": len(k1_insights),
                "patterns_detected": 0,
                "new_insights": 0,
                "skipped_reason": f"insufficient_k1_insights ({len(k1_insights)} < {ERL_K2_MIN_K1_INSIGHTS})",
                "batch_run_id": batch_run_id,
            }

        # 2) LLM input hazirla
        k1_summary_lines = []
        for ins in k1_insights:
            k1_summary_lines.append(f"- [{ins.title}] -> {ins.content[:200]}")
        user_message = (
            "Asagida kullanicinin son 24 saatte ifade ettigi ACIK kirmizi cizgiler:\n\n"
            + "\n".join(k1_summary_lines)
            + "\n\nBu acik ifadelere bakarak IMA EDILEN (implicit) bir kirmizi cizgi "
            "paterni var mi? Sema talimatina gore JSON dondur."
        )

        # 3) LLM provider hazirla (test fixture inject edebilir)
        if provider is None:
            try:
                from app.coach import build_provider  # build_provider app.coach'ta
                provider = build_provider()
            except Exception:
                return {
                    "k1_insights_fed": len(k1_insights),
                    "patterns_detected": 0,
                    "new_insights": 0,
                    "skipped_reason": "provider_unavailable",
                    "batch_run_id": batch_run_id,
                }

        # 4) LLM cagri - hata izolasyonu
        try:
            llm_response = provider.chat(
                system_prompt=ERL_K2_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
                tools=[],
            )
            response_text = getattr(llm_response, "text", None) or str(llm_response)
        except Exception as e:
            return {
                "k1_insights_fed": len(k1_insights),
                "patterns_detected": 0,
                "new_insights": 0,
                "skipped_reason": f"llm_error: {str(e)[:100]}",
                "batch_run_id": batch_run_id,
            }

        # 5) JSON parse + schema validation
        parsed = _erl_k2_parse_llm_json(response_text)
        if parsed is None:
            return {
                "k1_insights_fed": len(k1_insights),
                "patterns_detected": 0,
                "new_insights": 0,
                "skipped_reason": "llm_output_invalid_json",
                "batch_run_id": batch_run_id,
            }

        patterns = parsed["patterns"]
        if not patterns:
            return {
                "k1_insights_fed": len(k1_insights),
                "patterns_detected": 0,
                "new_insights": 0,
                "skipped_reason": "no_patterns_detected",
                "batch_run_id": batch_run_id,
            }

        # 6) Insight olarak yaz
        new_insights = 0
        for p in patterns:
            category = p["category"]
            description = p["description"]
            evidence = p["evidence_quotes"]
            confidence = p["confidence"]

            # BUG #104 fix: title dedup ANAHTARI (UNIQUE user_id+type+title). Eskiden volatil
            # LLM alıntısı (first_quote) title'a giriyordu → her nightly batch farklı title →
            # dedup başarısız → aynı kırmızı-çizgi için mükerrer insight birikip prompt top-5'ini
            # dolduruyordu. Title artık SADECE kategoriye bağlı (stabil) → aynı kategori tekrar
            # çalışınca UPSERT ile GÜNCELLENİR. Alıntı zaten content'te korunuyor (bilgi kaybı yok).
            title = f"Ima edilen kirmizi cizgi [{category}]"
            if len(title) > 200:
                title = title[:197] + "..."

            content_text = (
                f"LLM batch consolidation: {description}\n\n"
                f"Kanit alintilari ({len(evidence)} adet):\n"
                + "\n".join(f"  - \"{e}\"" for e in evidence)
                + f"\n\nLLM confidence: {confidence}. "
                f"Reasoning: {parsed['reasoning'][:200]}"
            )

            source_refs_list = [
                f"k2_batch:{batch_run_id}",
                f"k2_category:{category}",
                f"k2_confidence:{confidence}",
            ]

            _save_or_update_insight(
                db=db,
                user_id=user_id,
                insight_type="explicit_red_line",
                title=title,
                content=content_text,
                confidence_basis="pattern_grounded",  # K1 farki
                source_refs=source_refs_list,
                is_supporting_evidence=True,
                para_category="area",
                priority=ERL_K2_PRIORITY,
            )
            new_insights += 1

        return {
            "k1_insights_fed": len(k1_insights),
            "patterns_detected": len(patterns),
            "new_insights": new_insights,
            "skipped_reason": None,
            "batch_run_id": batch_run_id,
        }


# ============================================================================
# BOLUM 5 / PROMPT ENJEKSIYONU (Wave-2 H1G3+ tasarim)
# Sektor referansi: Mem0 selective retrieval + Letta core memory + OpenAI Realtime
# Karar: drop > truncate, verbatim icerik, top-5 by (sort_priority, last_evidence_at)
# ============================================================================

def format_insights_for_prompt(
    db: Session,
    user_id: int,
    max_tokens: int = 1500,
) -> str:
    """
    Wave-2 zengin yapili insight'lari V3_GOD_MODE_PROMPT context'i icin formatlar.

    Filtre: status='active' (dormant/invalidated/user_invalidated DAHIL DEGIL)
    Siralama: sort_priority DESC NULLS LAST, last_evidence_at DESC NULLS LAST
    Limit: Top 5 + 1500 token hard cap
    Strateji: Drop (truncate degil) - sektor 2026 standardi

    Returns:
        Bos string eger aktif insight yoksa.
        Aksi takdirde "## UZUN VADELI HAFIZA\\n..." formatinda metin.
    """
    from sqlalchemy import desc

    insights = (
        db.query(CoachInsight)
        .filter(
            CoachInsight.user_id == user_id,
            CoachInsight.status == "active",
        )
        .order_by(
            CoachInsight.sort_priority.desc().nullslast(),
            CoachInsight.last_evidence_at.desc().nullslast(),
        )
        .limit(5)
        .all()
    )

    if not insights:
        return ""

    # Token sayimi - tiktoken cl100k_base (Mem0/OpenAI standardi)
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        def count_tokens(s: str) -> int:
            return len(enc.encode(s))
    except ImportError:
        # Fallback: yaklasik 4 karakter = 1 token (TR icin ~%15 underestimate)
        def count_tokens(s: str) -> int:
            return max(1, len(s) // 4)

    header = (
        "## UZUN VADELI HAFIZA\n"
        "Bu kullanici hakkinda gecmis etkilesimlerden ogrenilen gerceklerdir.\n"
        "Sabit kurallar DEGIL, gozlemlerdir. Yeni kanit geldikce guncellenir.\n"
        "Her insight basliginda [TIP | GUVEN] etiketi vardir.\n"
    )

    used_tokens = count_tokens(header)
    shown_blocks = []
    dropped_count = 0

    for ins in insights:
        insight_type_label = (ins.insight_type or "GENEL").upper()
        confidence_label = ins.confidence_basis or "unknown"
        title_text = ins.title or "(baslik yok)"
        content_text = ins.content or "(icerik yok)"

        block = (
            f"\n[{insight_type_label} | GUVEN: {confidence_label}]\n"
            f"{title_text}\n"
            f"{content_text}\n"
        )
        block_tokens = count_tokens(block)

        if used_tokens + block_tokens > max_tokens:
            dropped_count = len(insights) - len(shown_blocks)
            break

        shown_blocks.append(block)
        used_tokens += block_tokens

    result = header + "".join(shown_blocks)

    if dropped_count > 0:
        result += f"\n(... {dropped_count} insight token butcesi sebebiyle gosterilmedi - DB'de mevcut)\n"

    return result

