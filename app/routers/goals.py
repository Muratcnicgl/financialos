"""
H2G5 Goal Engine — REST API (ADR-024)

13 endpoint:
  Goal CRUD      : POST /api/goals
                   GET  /api/goals
                   GET  /api/goals/{goal_id}
                   PATCH /api/goals/{goal_id}
                   DELETE /api/goals/{goal_id}
                   POST /api/goals/{goal_id}/refresh
  Allocation     : POST /api/goals/{goal_id}/allocations
                   GET  /api/goals/{goal_id}/allocations
                   DELETE /api/goals/allocations/{allocation_id}
  Rule           : POST /api/goals/{goal_id}/rules
                   GET  /api/goals/{goal_id}/rules
                   PATCH /api/goals/rules/{rule_id}
                   DELETE /api/goals/rules/{rule_id}

Tasarim:
  - app.dependencies.get_db + get_current_user (standart pattern)
  - debt_freedom POST'unda baseline_amount otomatik snapshot
  - goal_engine.refresh_goal flush eder, router commit eder
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.dependencies import get_db, get_current_user
from app.goal_engine import (
    calculate_baseline_for_debt_freedom,
    link_transaction,
    refresh_goal,
    unlink_transaction,
)


router = APIRouter(prefix="/api/goals", tags=["goals"])


# ============================================================
# GOAL CRUD
# ============================================================

@router.post("", response_model=schemas.GoalRead,
             status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: schemas.GoalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Yeni hedef yarat.

    debt_freedom: baseline_amount mevcut toplam kredi+kart bakiyesinden snapshot alınır.
    cash_target: baseline_amount NULL kalır, allocation toplamı izlenir.
    """
    goal = models.Goal(
        user_id=current_user.id,
        goal_type=payload.goal_type,
        title=payload.title,
        target_amount=payload.target_amount,
        target_date=payload.target_date,
        status="active",
    )

    if payload.goal_type == "debt_freedom":
        goal.baseline_amount = calculate_baseline_for_debt_freedom(
            current_user.id, db
        )

    db.add(goal)
    db.commit()
    db.refresh(goal)

    # İlk progress snapshot
    refresh_goal(goal.id, db)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("", response_model=List[schemas.GoalRead])
def list_goals(
    status_filter: Optional[str] = None,
    goal_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Tüm hedefler. Opsiyonel status + goal_type query filtresi."""
    q = db.query(models.Goal).filter(models.Goal.user_id == current_user.id)
    if status_filter:
        q = q.filter(models.Goal.status == status_filter)
    if goal_type:
        q = q.filter(models.Goal.goal_type == goal_type)
    return q.order_by(models.Goal.created_at.desc()).all()


@router.get("/{goal_id}", response_model=schemas.GoalRead)
def get_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.patch("/{goal_id}", response_model=schemas.GoalRead)
def update_goal(
    goal_id: int,
    payload: schemas.GoalUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)

    db.commit()
    db.refresh(goal)

    refresh_goal(goal.id, db)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
    return None


@router.post("/{goal_id}/refresh", response_model=schemas.GoalRead)
def refresh_goal_endpoint(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Progress cache'ini yeniden hesapla (manuel veya cron trigger)."""
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    result = refresh_goal(goal_id, db)
    db.commit()
    return result


# ============================================================
# ALLOCATION — manuel link / unlink
# ============================================================

@router.post("/{goal_id}/allocations",
             response_model=schemas.GoalAllocationRead,
             status_code=status.HTTP_201_CREATED)
def create_allocation(
    goal_id: int,
    payload: schemas.GoalAllocationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Bir transaction'ı manuel olarak goal'e bağla."""
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    tx = db.query(models.Transaction).filter(
        models.Transaction.id == payload.transaction_id,
        models.Transaction.user_id == current_user.id,
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    try:
        alloc = link_transaction(
            goal_id=goal_id,
            transaction_id=payload.transaction_id,
            amount=payload.amount,
            db=db,
            source="manual",
        )
        db.commit()
        return alloc
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This transaction is already linked to this goal",
        )


@router.get("/{goal_id}/allocations",
            response_model=List[schemas.GoalAllocationRead])
def list_allocations(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return (
        db.query(models.GoalAllocation)
        .filter(models.GoalAllocation.goal_id == goal_id)
        .order_by(models.GoalAllocation.created_at.desc())
        .all()
    )


@router.delete("/allocations/{allocation_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def delete_allocation(
    allocation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    alloc = db.query(models.GoalAllocation).filter(
        models.GoalAllocation.id == allocation_id,
    ).first()
    if not alloc:
        raise HTTPException(status_code=404, detail="Allocation not found")

    # Sadece kendi goal'ine ait allocation silinebilir
    goal = db.query(models.Goal).filter(
        models.Goal.id == alloc.goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=403, detail="Access denied")

    unlink_transaction(allocation_id, db)
    db.commit()
    return None


# ============================================================
# RULE CRUD
# ============================================================

@router.post("/{goal_id}/rules",
             response_model=schemas.GoalRuleRead,
             status_code=status.HTTP_201_CREATED)
def create_rule(
    goal_id: int,
    payload: schemas.GoalRuleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    rule = models.GoalRule(
        goal_id=goal_id,
        name=payload.name,
        priority=payload.priority,
        criteria=payload.criteria,
        allocation_type=payload.allocation_type,
        allocation_value=payload.allocation_value,
        is_active=payload.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{goal_id}/rules",
            response_model=List[schemas.GoalRuleRead])
def list_rules(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return (
        db.query(models.GoalRule)
        .filter(models.GoalRule.goal_id == goal_id)
        .order_by(models.GoalRule.priority.asc(), models.GoalRule.id.asc())
        .all()
    )


@router.patch("/rules/{rule_id}", response_model=schemas.GoalRuleRead)
def update_rule(
    rule_id: int,
    payload: schemas.GoalRuleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rule = db.query(models.GoalRule).filter(
        models.GoalRule.id == rule_id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Kural sahibinin goal'i current_user'a ait mi?
    goal = db.query(models.Goal).filter(
        models.Goal.id == rule.goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=403, detail="Access denied")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rule = db.query(models.GoalRule).filter(
        models.GoalRule.id == rule_id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    goal = db.query(models.Goal).filter(
        models.Goal.id == rule.goal_id,
        models.Goal.user_id == current_user.id,
    ).first()
    if not goal:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(rule)
    db.commit()
    return None
