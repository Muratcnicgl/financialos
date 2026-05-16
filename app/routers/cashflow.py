"""
GET /api/cashflow/forecast — Nakit akışı tahmini endpoint'i.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.cashflow import generate_forecast
from app.dependencies import get_db, get_current_user
from app.models import User

router = APIRouter(prefix="/api/cashflow", tags=["cashflow"])


# ============================================================
# RESPONSE ŞEMALARI
# ============================================================

class ForecastEventOut(BaseModel):
    date: str
    type: str          # "receivable" | "payable"
    amount: float
    label: str
    source_type: str   # income | recurring_expense | receivable | payable | loan
    source_id: int


class ForecastDayOut(BaseModel):
    date: str
    opening_balance: float
    closing_balance: float
    inflows: float
    outflows: float
    events: List[ForecastEventOut]
    crunch: bool


class ForecastSankeyNode(BaseModel):
    id: int
    name: str
    type: str


class ForecastSankeyLink(BaseModel):
    source: int
    target: int
    value: float
    label: str


class ForecastSankey(BaseModel):
    nodes: List[ForecastSankeyNode]
    links: List[ForecastSankeyLink]


class ForecastSummary(BaseModel):
    lowest_balance: float
    lowest_date: str
    total_receivable: float
    total_payable: float
    net_flow: float
    crunch_count: int
    crunch_dates: List[str]
    opening_balance: float


class ForecastResponse(BaseModel):
    horizon_days: int
    start_date: str
    end_date: str
    currency: str
    days: List[ForecastDayOut]
    summary: ForecastSummary
    sankey: ForecastSankey


# ============================================================
# ENDPOINT
# ============================================================

@router.get("/forecast", response_model=ForecastResponse)
def cashflow_forecast(
    days: int = Query(default=60, ge=1, le=180,
                      description="Kaç günlük tahmin (1-180, varsayılan 60)"),
    account_id: Optional[int] = Query(default=None,
                                      description="Belirli hesap ID; None = tüm nakit hesaplar"),
    include: str = Query(
        default="incomes,expenses,receivables,payables",
        description="Filtre chipsleri (csv): incomes,expenses,receivables,payables",
    ),
    crunch_threshold: float = Query(
        default=0.0,
        description="Bu TL tutarının altına düşen günler crunch=True (varsayılan 0)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Gelecek N gün nakit akışı tahmini.

    Kaynak: RecurringIncome, RecurringExpense, PersonalDebt, kredi taksitleri.
    Hariç: yatırım hesapları, kredi kartı taksit döngüsü (Wave-3).
    """
    include_set = {s.strip() for s in include.split(",") if s.strip()}

    result = generate_forecast(
        db=db,
        user_id=current_user.id,
        horizon_days=days,
        account_id=account_id,
        include=include_set,
        crunch_threshold=crunch_threshold,
    )

    days_out: list[ForecastDayOut] = []
    for day in result["days"]:
        events_out = [
            ForecastEventOut(
                date=ev.date.isoformat(),
                type="receivable" if ev.amount >= 0 else "payable",
                amount=ev.amount,
                label=ev.label,
                source_type=ev.source_type,
                source_id=ev.source_id,
            )
            for ev in day.events
        ]
        days_out.append(ForecastDayOut(
            date=day.date.isoformat(),
            opening_balance=day.opening_balance,
            closing_balance=day.closing_balance,
            inflows=day.inflows,
            outflows=day.outflows,
            events=events_out,
            crunch=day.crunch,
        ))

    s = result["sankey"]
    sankey = ForecastSankey(
        nodes=[ForecastSankeyNode(**n) for n in s["nodes"]],
        links=[ForecastSankeyLink(**lnk) for lnk in s["links"]],
    )

    return ForecastResponse(
        horizon_days=result["horizon_days"],
        start_date=result["start_date"],
        end_date=result["end_date"],
        currency=result["currency"],
        days=days_out,
        summary=ForecastSummary(**result["summary"]),
        sankey=sankey,
    )
