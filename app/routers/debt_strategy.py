"""
GET /api/debt-strategy/compare?extra_monthly=0

Snowball vs Avalanche karsilastirmasi.
Algoritma deterministik (app/debt_strategy.py), endpoint sadece HTTP wrapper.
ADR-001: algoritma karar verir (sektor standardi matematik), kullanici secer.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.debt_strategy import compare_strategies
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debt-strategy", tags=["debt-strategy"])


class DebtItemOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    account_id: int
    name: str
    account_type: str
    balance: float
    interest_rate_monthly: float
    min_payment: float


class StrategyOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    strategy: str
    order: list[int]
    months_to_freedom: int
    total_interest_paid: float
    total_paid: float
    payoff_date: Optional[str] = None
    debt_payoff_months: dict


class ComparisonOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    interest_saved_with_avalanche: float
    months_difference: int
    recommendation_note: str


class DebtStrategyResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    debts: list[DebtItemOut]
    snowball: Optional[StrategyOut] = None
    avalanche: Optional[StrategyOut] = None
    comparison: ComparisonOut


@router.get("/compare", response_model=DebtStrategyResponse)
def compare(
    extra_monthly: float = Query(
        0.0, ge=0.0, le=100_000.0,
        description="Aylik ekstra odeme (0 - 100000 TL)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DebtStrategyResponse:
    """
    Snowball ve Avalanche stratejilerini hesapla, yan yana karsilastir.

    extra_monthly: Kullanicinin minimum odemeler uzerine ekleyebilecegi para.
                   0 = mevcut taksitlerle, ekstra yok.
    """
    try:
        result = compare_strategies(db, current_user.id, extra_monthly)
    except Exception as e:
        logger.exception("debt-strategy compare failed user_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail=f"Strateji hesabi hatasi: {e}")

    logger.info(
        "debt-strategy compare user_id=%s debts=%d extra=%.2f",
        current_user.id, len(result['debts']), extra_monthly,
    )
    return DebtStrategyResponse(**result)
