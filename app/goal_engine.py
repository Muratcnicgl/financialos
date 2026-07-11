"""
H2G5 Goal Engine — ADR-024
Allocation-Based Goal Tracking (Monarch Money Goals 3.0 pattern).

Sorumluluklar:
  - refresh_goal        : tek goal'in progress cache'ini yenile
  - compute_progress    : tipe göre (debt_freedom | cash_target) dispatch
  - calculate_baseline_for_debt_freedom : yeni goal yaratımında snapshot
  - link_transaction    : manuel GoalAllocation yarat
  - unlink_transaction  : GoalAllocation sil

Tasarım ilkeleri:
  - db.flush() kullanır, db.commit() kullanmaz — commit caller'ın sorumluluğu
  - ADR-001: saf Python hesap, LLM yok
  - debt_freedom baseline = Account(loan + credit_card) toplam bakiyesi
  - cash_target progress = GoalAllocation toplamı / target_amount
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app import models
from app.models import Account, AccountType, GoalAllocation, PersonalDebt


# ============================================================
# BASELINE — debt_freedom için goal yaratım anında çağrılır
# ============================================================

def calculate_baseline_for_debt_freedom(user_id: int, db: Session) -> Decimal:
    """Kullanıcının aktif kredi + kart borcu toplamı (loan + credit_card, balance > 0)."""
    total = db.query(
        func.coalesce(func.sum(Account.balance), 0)
    ).filter(
        Account.user_id == user_id,
        Account.account_type.in_([AccountType.loan, AccountType.credit_card]),
        Account.balance > 0,
    ).scalar()
    return Decimal(str(total))


# ============================================================
# PROGRESS HESAPLAMA
# ============================================================

def compute_progress(goal: models.Goal, db: Session) -> dict:
    """Goal tipine göre dispatch eder.
    Dönüş: {current_amount, progress_percent, projected_completion_date}"""
    if goal.goal_type == "debt_freedom":
        return _compute_debt_freedom(goal, db)
    elif goal.goal_type == "cash_target":
        return _compute_cash_target(goal, db)
    else:
        raise ValueError(f"Unknown goal_type: {goal.goal_type}")


def _compute_debt_freedom(goal: models.Goal, db: Session) -> dict:
    """debt_freedom ilerleme:

    progress = (baseline - current_debt) / baseline × 100

    baseline_amount: goal yaratım anındaki toplam kredi/kart bakiyesi.
    current_debt: şimdiki toplam kredi/kart bakiyesi.
    """
    if not goal.baseline_amount or goal.baseline_amount == 0:
        return {
            "current_amount": Decimal("0"),
            "progress_percent": Decimal("0"),
            "projected_completion_date": None,
        }

    current_debt = db.query(
        func.coalesce(func.sum(Account.balance), 0)
    ).filter(
        Account.user_id == goal.user_id,
        Account.account_type.in_([AccountType.loan, AccountType.credit_card]),
        Account.balance > 0,
    ).scalar()
    current_debt = Decimal(str(current_debt))

    paid_off = goal.baseline_amount - current_debt
    paid_off = max(paid_off, Decimal("0"))  # yeni borç eklenince negatife düşmez
    progress = min((paid_off / goal.baseline_amount) * Decimal("100"), Decimal("100"))

    projected = _project_debt_freedom(goal, db)

    return {
        "current_amount": paid_off,
        "progress_percent": progress.quantize(Decimal("0.01")),
        "projected_completion_date": projected,
    }


def _project_debt_freedom(goal: models.Goal, db: Session) -> Optional[date]:
    """debt_strategy.compare_strategies Snowball sonucundan tahmini bitiş tarihi."""
    if not goal.user_id:
        return None
    try:
        from app.debt_strategy import compare_strategies
        result = compare_strategies(db=db, user_id=goal.user_id, extra_monthly=0.0)
        snowball = result.get("snowball")
        # BUG #066 fix (GE-001): compare_strategies DICT döner (_result_to_dict, key
        # 'months_to_freedom'); attribute erişimi (snowball.months_to_freedom) AttributeError
        # atıp bare-except tarafından yutuluyordu → projected_completion_date HER ZAMAN None idi.
        if snowball and snowball["months_to_freedom"] < 600:
            return date.today() + timedelta(days=int(snowball["months_to_freedom"] * 30))
    except Exception:
        pass
    return None


def _compute_cash_target(goal: models.Goal, db: Session) -> dict:
    """cash_target ilerleme: GoalAllocation toplamı / target_amount.

    amount > 0: katkı (contribution)
    amount < 0: çekim (withdrawal)
    """
    alloc_sum = db.query(
        func.coalesce(func.sum(GoalAllocation.amount), 0)
    ).filter(GoalAllocation.goal_id == goal.id).scalar()
    current = Decimal(str(alloc_sum))

    if goal.target_amount == 0:
        progress = Decimal("0")
    else:
        progress = (current / goal.target_amount) * Decimal("100")
        progress = max(min(progress, Decimal("100")), Decimal("0"))

    projected = _project_cash_completion(goal, current, db)

    return {
        "current_amount": current,
        "progress_percent": progress.quantize(Decimal("0.01")),
        "projected_completion_date": projected,
    }


def _project_cash_completion(
    goal: models.Goal, current: Decimal, db: Session
) -> Optional[date]:
    """Son 90 günlük allocation hızından tahmini tamamlanma tarihi."""
    if current >= goal.target_amount:
        return None

    cutoff = datetime.utcnow() - timedelta(days=90)
    recent_sum = db.query(
        func.coalesce(func.sum(GoalAllocation.amount), 0)
    ).filter(
        and_(
            GoalAllocation.goal_id == goal.id,
            GoalAllocation.created_at >= cutoff,
        )
    ).scalar()
    recent_sum = Decimal(str(recent_sum))

    if recent_sum <= 0:
        return None

    # BUG #105 fix: hız = recent_sum / GERÇEK katkı süresi (sabit 90 DEĞİL). Genç bir goal'de
    # (örn. 10 gün önce açılmış, 3000 birikmiş) sabit 90'a bölmek hızı ~9x düşük gösterip
    # tamamlanmayı çok uzağa atıyordu. Penceredeki ilk allocation'dan bugüne olan span kullanılır
    # (en az 1, en çok 90 gün).
    first_alloc = db.query(func.min(GoalAllocation.created_at)).filter(
        and_(
            GoalAllocation.goal_id == goal.id,
            GoalAllocation.created_at >= cutoff,
        )
    ).scalar()
    if first_alloc:
        span_days = (datetime.utcnow() - first_alloc).days
        span_days = max(1, min(90, span_days))
    else:
        span_days = 90

    daily_rate = recent_sum / Decimal(str(span_days))
    remaining = goal.target_amount - current
    days_needed = int(remaining / daily_rate)

    if days_needed > 365 * 10:
        return None

    return date.today() + timedelta(days=days_needed)


def sinking_fund_plan(target_amount, target_date, current_amount, today: Optional[date] = None) -> Optional[dict]:
    """
    FEAT-003 (sinking funds / YNAB "true expenses"): target_date'li bir birikim hedefi için
    AYLIK GEREKEN katkıyı hesaplar. Düzensiz büyük gideri (MTV, sigorta, tatil, bayram) aylık
    küçük parçalara böler → "büyük fatura şoku" biter. Salt hesap (ADR-001, LLM yok).

    Dönüş (target_date varsa): {aylik_gereken: Decimal, kalan_ay: int, gecikmis: bool, tamamlandi: bool}
    target_date yoksa None (klasik cash_target — sinking fund değil).
    """
    if target_date is None:
        return None
    if today is None:
        today = date.today()

    target = Decimal(str(target_amount))
    current = Decimal(str(current_amount))
    remaining = target - current
    if remaining <= 0:
        return {"aylik_gereken": Decimal("0.00"), "kalan_ay": 0, "gecikmis": False, "tamamlandi": True}

    # Bugünden target_date'e kalan TAM ay sayısı (gün eşiği dahil)
    months = (target_date.year - today.year) * 12 + (target_date.month - today.month)
    if target_date.day < today.day:
        months -= 1

    if months <= 0:
        # Vade bu ay ya da geçmiş → kalanın TÜMÜ şimdi gerekli
        return {
            "aylik_gereken": remaining.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "kalan_ay": 0,
            "gecikmis": target_date < today,
            "tamamlandi": False,
        }

    monthly = (remaining / Decimal(months)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return {"aylik_gereken": monthly, "kalan_ay": months, "gecikmis": False, "tamamlandi": False}


# ============================================================
# REFRESH — Goal cache alanlarını güncelle
# ============================================================

def refresh_goal(goal_id: int, db: Session) -> models.Goal:
    """Progress hesapla, cache'i yaz, flush et (commit caller'a bırakılır)."""
    goal = db.query(models.Goal).filter(models.Goal.id == goal_id).first()
    if not goal:
        raise ValueError(f"Goal {goal_id} not found")

    result = compute_progress(goal, db)
    goal.current_amount = result["current_amount"]
    goal.progress_percent = result["progress_percent"]
    goal.projected_completion_date = result["projected_completion_date"]
    goal.last_refreshed_at = datetime.utcnow()

    if goal.progress_percent >= Decimal("100") and goal.status == "active":
        goal.status = "achieved"
        goal.achieved_at = datetime.utcnow()

    db.flush()
    return goal


# ============================================================
# MANUEL ALLOCATION YÖNETİMİ
# ============================================================

def link_transaction(
    goal_id: int,
    transaction_id: int,
    amount: Decimal,
    db: Session,
    source: str = "manual",
    rule_id: Optional[int] = None,
) -> GoalAllocation:
    """Transaction'ı goal'e bağla, progress cache'ini tazele.

    Aynı (goal_id, transaction_id) zaten varsa IntegrityError fırlatır.
    Caller yakalamak zorunda değil — SQLite unique constraint enforce eder.
    """
    alloc = GoalAllocation(
        goal_id=goal_id,
        transaction_id=transaction_id,
        amount=amount,
        source=source,
        rule_id=rule_id,
        created_at=datetime.utcnow(),
    )
    db.add(alloc)
    db.flush()
    db.refresh(alloc)
    refresh_goal(goal_id, db)
    return alloc


def unlink_transaction(allocation_id: int, db: Session) -> int:
    """Allocation kaydını sil, progress cache'ini tazele. Dönüş: goal_id."""
    alloc = db.query(GoalAllocation) \
              .filter(GoalAllocation.id == allocation_id).first()
    if not alloc:
        raise ValueError(f"Allocation {allocation_id} not found")
    goal_id = alloc.goal_id
    db.delete(alloc)
    db.flush()
    refresh_goal(goal_id, db)
    return goal_id
