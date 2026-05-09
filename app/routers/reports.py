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

from calendar import monthrange
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import (
    Transaction, TransactionType, User, NetWorthSnapshot,
    Account, AccountType, PersonalDebt, DebtDirection,
    RecurringIncome, RecurringExpense,
)

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
            "investment_value": round(float(r.investment_value or 0), 2),
        }
        for r in rows
    ]
    return {"items": items, "days": days}


# ============================================================
# ALACAK-BORC TAKVIMI
# ============================================================

def _next_occurrences(today: date, horizon: date, day_of_month: int) -> list[date]:
    """today <= d <= horizon olan tüm aylık tekrar tarihlerini döner."""
    results = []
    cur = today.replace(day=1)
    while cur <= horizon:
        last = monthrange(cur.year, cur.month)[1]
        candidate = date(cur.year, cur.month, min(day_of_month, last))
        if today <= candidate <= horizon:
            results.append(candidate)
        cur = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    return results


@router.get("/upcoming-cashflow")
def upcoming_cashflow(
    days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Gelecek N günde vadesi gelen alacak, borç, kredi taksiti ve
    tekrarlayan gelir/gider kalemlerini döner.
    """
    today = date.today()
    horizon = today + timedelta(days=days)
    items = []

    # --- PersonalDebt: alacaklar (receivable) ---
    for d in db.query(PersonalDebt).filter(
        PersonalDebt.user_id == current_user.id,
        PersonalDebt.direction == DebtDirection.receivable,
        PersonalDebt.is_paid == False,   # noqa: E712
        PersonalDebt.due_date.isnot(None),
        PersonalDebt.due_date <= horizon,
    ).all():
        label = d.counterparty + (f" — {d.description}" if d.description else "")
        items.append({"date": d.due_date.isoformat(), "type": "receivable",
                      "amount": d.amount, "label": label, "source": "personal_debt"})

    # --- PersonalDebt: borçlar (payable) ---
    for d in db.query(PersonalDebt).filter(
        PersonalDebt.user_id == current_user.id,
        PersonalDebt.direction == DebtDirection.payable,
        PersonalDebt.is_paid == False,   # noqa: E712
        PersonalDebt.due_date.isnot(None),
        PersonalDebt.due_date <= horizon,
    ).all():
        label = d.counterparty + (f" — {d.description}" if d.description else "")
        items.append({"date": d.due_date.isoformat(), "type": "payable",
                      "amount": -d.amount, "label": label, "source": "personal_debt"})

    # --- Loan hesapları: next_payment_date ---
    for acc in db.query(Account).filter(
        Account.user_id == current_user.id,
        Account.account_type == AccountType.loan,
        Account.next_payment_date.isnot(None),
        Account.next_payment_date <= horizon,
    ).all():
        items.append({"date": acc.next_payment_date.isoformat(), "type": "payable",
                      "amount": -(acc.monthly_payment or 0), "label": acc.name, "source": "loan"})

    # --- RecurringIncome: aylık tekrar tarihleri ---
    for inc in db.query(RecurringIncome).filter(
        RecurringIncome.user_id == current_user.id,
        RecurringIncome.is_active == True,   # noqa: E712
    ).all():
        for d in _next_occurrences(today, horizon, inc.day_of_month):
            items.append({"date": d.isoformat(), "type": "receivable",
                          "amount": inc.amount, "label": inc.name, "source": "income"})

    # --- RecurringExpense: aylık tekrar tarihleri ---
    for exp in db.query(RecurringExpense).filter(
        RecurringExpense.user_id == current_user.id,
        RecurringExpense.is_active == True,   # noqa: E712
    ).all():
        for d in _next_occurrences(today, horizon, exp.day_of_month):
            items.append({"date": d.isoformat(), "type": "payable",
                          "amount": -exp.amount, "label": exp.name, "source": "recurring_expense"})

    # Sıralama: tarih ASC, tutar mutlak değer DESC
    items.sort(key=lambda x: (x["date"], -abs(x["amount"])))

    total_receivable = sum(i["amount"] for i in items if i["amount"] > 0)
    total_payable = sum(i["amount"] for i in items if i["amount"] < 0)

    return {
        "items": items,
        "summary": {
            "total_receivable": round(total_receivable, 2),
            "total_payable": round(total_payable, 2),
            "net_flow": round(total_receivable + total_payable, 2),
            "items_count": len(items),
        },
        "days": days,
        "today": today.isoformat(),
    }
