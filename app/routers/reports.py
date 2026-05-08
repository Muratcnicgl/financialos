"""
Reports router — Gelir/Gider kategori dagilimi.

GET /api/reports/category-breakdown
  Parametreler:
    days: 1-365 (varsayilan 30)
    type: expense | income | both (varsayilan expense)
  Doner:
    {items: [{category, total, count, percentage}], grand_total, days, type}
  Siralama: total DESC
  "both" transferleri icermez (sadece gelir + gider).
"""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import Transaction, TransactionType, User, NetWorthSnapshot

router = APIRouter(prefix="/api/reports", tags=["reports"])


class CategoryItem(BaseModel):
    category: str
    total: float
    count: int
    percentage: float


class CategoryBreakdownResponse(BaseModel):
    items: list[CategoryItem]
    grand_total: float
    days: int
    type: str


@router.get("/category-breakdown", response_model=CategoryBreakdownResponse)
def category_breakdown(
    days: int = Query(default=30, ge=1, le=365),
    type: Literal["expense", "income", "both"] = Query(default="expense"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since = date.today() - timedelta(days=days)

    q = db.query(
        func.coalesce(Transaction.category, "(kategorisiz)").label("category"),
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("cnt"),
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date >= since,
    )

    if type == "expense":
        q = q.filter(Transaction.transaction_type == TransactionType.expense)
    elif type == "income":
        q = q.filter(Transaction.transaction_type == TransactionType.income)
    else:
        q = q.filter(Transaction.transaction_type.in_(
            [TransactionType.expense, TransactionType.income]
        ))

    rows = q.group_by(
        func.coalesce(Transaction.category, "(kategorisiz)")
    ).order_by(
        func.sum(Transaction.amount).desc()
    ).all()

    grand_total = sum(r.total for r in rows)

    items = [
        CategoryItem(
            category=r.category,
            total=round(r.total, 2),
            count=r.cnt,
            percentage=round(r.total / grand_total * 100, 1) if grand_total > 0 else 0.0,
        )
        for r in rows
    ]

    return CategoryBreakdownResponse(
        items=items,
        grand_total=round(grand_total, 2),
        days=days,
        type=type,
    )


# ============================================================
# NET DEGER TREND
# ============================================================

@router.get("/net-worth-trend")
def net_worth_trend(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Son N gündeki günlük net değer snapshot'larını döner.
    NetWorthSnapshot tablosundan, cockpit her açıldığında yazılan veriler.
    Geçmiş veriler scripts/backfill_net_worth.py ile doldurulur.
    """
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(NetWorthSnapshot)
        .filter(
            NetWorthSnapshot.user_id == current_user.id,
            NetWorthSnapshot.snapshot_date >= since,
        )
        .order_by(NetWorthSnapshot.snapshot_date.asc())
        .all()
    )
    items = [
        {
            "date": r.snapshot_date.isoformat(),
            "net_worth_seen": round(float(r.net_worth_seen), 2),
            "net_worth_full": round(float(r.net_worth_full), 2),
        }
        for r in rows
    ]
    return {"items": items, "days": days}
