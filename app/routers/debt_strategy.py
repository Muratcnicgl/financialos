"""
GET /api/debt-strategy/compare?extra_monthly=0

Snowball vs Avalanche karsilastirmasi.
Algoritma deterministik (app/debt_strategy.py), endpoint sadece HTTP wrapper.
ADR-001: algoritma karar verir (sektor standardi matematik), kullanici secer.

GUNCELLEMELER:
- BUG #223 fix (D03): uclar `workspace_scope` blogu icine hic girmiyordu → `collect_debts`
  icindeki `_scope` koprusu (M72) her zaman legacy `user_id` dalina dusuyor, aile
  workspace'i secili iken KISISEL borclar uzerinde snowball/avalanche/konsolidasyon
  kosuyordu (cockpit ayni ekranda "0 TL borc" derken). Uyelik dogrulamasi da yoktu.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.rules_engine import workspace_scope  # BUG #223: aktif workspace kapsami
from app.workspace_deps import active_workspace_id  # BUG #223: uyelik dogrulama + ws cozumu
from app.debt_strategy import (
    compare_strategies, collect_debts, simulate_consolidation,
    simulate_purchase_opportunity_cost,
)
from app.models import User
from app.money_format import para_etiketi  # BUG #256 (H4): para etiketi tek kaynak

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
        description=f"Aylik ekstra odeme (0 - 100000 {para_etiketi()})",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # BUG #223
) -> DebtStrategyResponse:
    """
    Snowball ve Avalanche stratejilerini hesapla, yan yana karsilastir.

    extra_monthly: Kullanicinin minimum odemeler uzerine ekleyebilecegi para.
                   0 = mevcut taksitlerle, ekstra yok.

    Kapsam: aktif workspace (X-Workspace-Id; yoksa personal). BUG #223.
    """
    try:
        with workspace_scope(ws_id):  # BUG #223: cockpit ile ayni kapsam kaynagi
            result = compare_strategies(db, current_user.id, extra_monthly)
    except Exception as e:
        logger.exception("debt-strategy compare failed user_id=%s", current_user.id)
        raise HTTPException(status_code=500,  # BUG #175: ham exception metni sızmaz (loglandı)
                            detail="Strateji hesabi su anda yapilamiyor. Lutfen tekrar deneyin.")

    logger.info(
        "debt-strategy compare user_id=%s debts=%d extra=%.2f",
        current_user.id, len(result['debts']), extra_monthly,
    )
    return DebtStrategyResponse(**result)


@router.get("/consolidation")
def consolidation(
    rate: float = Query(
        ..., ge=0.0, le=20.0,
        description="Teklif edilen konsolidasyon kredisi AYLIK faiz oranı (%/ay, 0-20)",
    ),
    term: int = Query(
        ..., ge=1, le=360,
        description="Konsolidasyon kredisi vadesi (ay, 1-360)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # BUG #223
) -> dict:
    """
    FEAT-014: Tüm borçları tek krediye (verilen oran + vade) toplayınca aylık taksit +
    toplam faiz. Nötr karşılaştırma — ağırlıklı ortalama orana göre avantajlı mı gösterir.
    Tavsiye DEĞİL: kullanıcı teklif edilen oran/vadeyi girer, sistem matematiği yapar.

    <2 borç → 404 (konsolidasyon en az iki borç ister).
    Kapsam: aktif workspace (X-Workspace-Id; yoksa personal). BUG #223.
    """
    with workspace_scope(ws_id):  # BUG #223
        debts = collect_debts(db, current_user.id)
    result = simulate_consolidation(debts, rate, term)
    if result is None:
        raise HTTPException(status_code=404, detail="Konsolidasyon için en az iki aktif borç gerekir.")
    logger.info("consolidation sim user_id=%s rate=%.2f term=%d", current_user.id, rate, term)
    return result


@router.get("/opportunity-cost")
def opportunity_cost(
    amount: float = Query(
        ..., gt=0.0, le=10_000_000.0,
        description=f"Harcamayı düşündüğün tutar ({para_etiketi()}) — borca ödemenin alternatif maliyeti",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # BUG #223
) -> dict:
    """
    FEAT-030: `amount` TL'yi harcamak vs en yüksek faizli borca ödemek — borçsuzluk tarihine
    ve toplam faize etkisi. İmpuls harcamayı somut maliyetle yavaşlatan nötr what-if aracı
    (harcama emri değil). Aktif borç yoksa 404.

    Kapsam: aktif workspace (X-Workspace-Id; yoksa personal). BUG #223.
    """
    with workspace_scope(ws_id):  # BUG #223
        debts = collect_debts(db, current_user.id)
    result = simulate_purchase_opportunity_cost(debts, amount)
    if result is None:
        raise HTTPException(status_code=404, detail="Fırsat maliyeti için aktif borç gerekir.")
    logger.info("opportunity-cost sim user_id=%s amount=%.2f", current_user.id, amount)
    return result
