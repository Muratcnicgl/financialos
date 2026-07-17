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
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.rules_engine import (
    generate_monthly_summary, calculate_networth_attribution, calculate_real_networth,
    workspace_scope,  # M43
)
from app.workspace_deps import active_workspace_id, scope_filter  # M43
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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    since = date.today() - timedelta(days=days)

    # BUG #073 fix (P0-11/RRE-001): transaction_type de select+group_by'a eklendi. "both"
    # modunda aynı kategori adlı gelir + gider tek 'total'da toplanıp yön bilgisini yok
    # ediyordu (örn. 1000 gelir + 200 gider → tek satır 1200); artık ayrı, etiketli satırlar.
    q = db.query(
        func.coalesce(Transaction.category, "(kategorisiz)").label("category"),
        Transaction.transaction_type.label("ttype"),
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("cnt"),
    ).filter(
        scope_filter(Transaction, current_user.id, ws_id),
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
        func.coalesce(Transaction.category, "(kategorisiz)"),
        Transaction.transaction_type,
    ).order_by(
        func.sum(Transaction.amount).desc()
    ).all()

    grand_total = sum(r.total for r in rows)

    def _label(r):
        # "both" modunda geliri giderden ayırt et (yön etiketi)
        if type == "both":
            yon = "gelir" if r.ttype == TransactionType.income else "gider"
            return f"{r.category} ({yon})"
        return r.category

    items = [
        CategoryItem(
            category=_label(r),
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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
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
            scope_filter(NetWorthSnapshot, current_user.id, ws_id),
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


@router.get("/net-worth-attribution")
def net_worth_attribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """
    FEAT-021: Bu ayki net değer değişimini sürücülerine ayrıştırır (nakit, kart/kredi ödeme,
    yatırım, alacak). Yeterli snapshot geçmişi yoksa {available: false}.
    """
    with workspace_scope(ws_id):  # M43
        r = calculate_networth_attribution(current_user.id, date.today(), db)
    if r is None:
        return {"available": False}
    return {"available": True, **r}


@router.get("/real-net-worth")
def real_net_worth(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """
    FEAT-024: Enflasyon-düzeltilmiş (reel) net değer — nominal vs reel değişim + enflasyon etkisi.
    Türkiye'de servetin gerçek yönünü gösterir. Yeterli snapshot geçmişi yoksa {available: false}.
    """
    with workspace_scope(ws_id):  # M43
        r = calculate_real_networth(current_user.id, date.today(), db)
    if r is None:
        return {"available": False}
    return {"available": True, **r}


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
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
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
        scope_filter(PersonalDebt, current_user.id, ws_id),
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
        scope_filter(PersonalDebt, current_user.id, ws_id),
        PersonalDebt.direction == DebtDirection.payable,
        PersonalDebt.is_paid == False,   # noqa: E712
        PersonalDebt.due_date.isnot(None),
        PersonalDebt.due_date <= horizon,
    ).all():
        label = d.counterparty + (f" — {d.description}" if d.description else "")
        items.append({"date": d.due_date.isoformat(), "type": "payable",
                      "amount": -d.amount, "label": label, "source": "personal_debt"})

    # --- Loan hesapları: ufuk boyunca AYLIK taksitler (BUG #074 fix / P0-12) ---
    # Eskiden sadece next_payment_date'teki TEK taksit ekleniyordu; 180 günlük ufukta
    # 5 kredinin her biri ~6 taksit öderken rapor 1'er gösterip total_payable'ı ciddi eksik,
    # net_flow'u iyimser çıkarıyordu ("sanal zenginlik" ihlali). Artık next_payment_date'ten
    # başlayarak ufuk sonuna kadar, kalan taksit sayısıyla sınırlı aylık taksitler üretilir.
    import calendar as _cal
    for acc in db.query(Account).filter(
        scope_filter(Account, current_user.id, ws_id),
        Account.account_type == AccountType.loan,
        Account.next_payment_date.isnot(None),
    ).all():
        pay = acc.monthly_payment or 0
        if pay <= 0:
            continue
        remaining = acc.remaining_installments if acc.remaining_installments is not None else 999
        cur = acc.next_payment_date
        pay_day = cur.day
        count = 0
        while cur <= horizon and count < remaining:
            items.append({"date": cur.isoformat(), "type": "payable",
                          "amount": -pay, "label": acc.name, "source": "loan"})
            count += 1
            ny = cur.year + (cur.month // 12)
            nm = (cur.month % 12) + 1
            cur = date(ny, nm, min(pay_day, _cal.monthrange(ny, nm)[1]))

    # --- RecurringIncome: aylık tekrar tarihleri ---
    for inc in db.query(RecurringIncome).filter(
        scope_filter(RecurringIncome, current_user.id, ws_id),
        RecurringIncome.is_active == True,   # noqa: E712
    ).all():
        for d in _next_occurrences(today, horizon, inc.day_of_month):
            items.append({"date": d.isoformat(), "type": "receivable",
                          "amount": inc.amount, "label": inc.name, "source": "income"})

    # --- RecurringExpense: aylık tekrar tarihleri ---
    for exp in db.query(RecurringExpense).filter(
        scope_filter(RecurringExpense, current_user.id, ws_id),
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


# ============================================================
# AYLIK ÖZET (A3) — matematik rules_engine.generate_monthly_summary'de
# ============================================================

@router.get("/monthly-summary")
def monthly_summary(
    year: Optional[int] = Query(default=None, ge=2000, le=2100),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """
    A3: Aylık özet rapor — gelir/gider/net değişim + gider kategori dağılımı +
    önceki aya göre trend. year/month verilmezse içinde bulunulan ay.
    Hesap rules_engine'de (mimari kural); router yalnız parametre + delege eder.
    """
    today = date.today()
    y = year or today.year
    m = month or today.month
    with workspace_scope(ws_id):  # M43
        return generate_monthly_summary(current_user.id, y, m, db)
