"""
Pydantic v2 şemaları — API request/response doğrulama.
ORM modellerinden bağımsız, frontend ile veri sözleşmesi.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


# === ORTAK ===

class TimestampedSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: Optional[datetime] = None


# === ACCOUNT ===

class AccountBase(BaseModel):
    name: str
    account_type: Literal["cash", "credit_card", "loan", "investment"]
    balance: float = 0.0
    notes: Optional[str] = None

    # Kart
    credit_limit: Optional[float] = None
    statement_day: Optional[int] = Field(default=None, ge=1, le=31)
    payment_day: Optional[int] = Field(default=None, ge=1, le=31)

    # Kredi
    interest_rate: Optional[float] = None
    monthly_payment: Optional[float] = None
    remaining_installments: Optional[int] = None
    next_payment_date: Optional[date] = None

    # Yatırım
    fund_code: Optional[str] = None
    lot_count: Optional[float] = None
    cost_per_lot: Optional[float] = None
    current_price: Optional[float] = None
    is_emanet: bool = False


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    balance: Optional[float] = None
    notes: Optional[str] = None
    credit_limit: Optional[float] = None
    statement_day: Optional[int] = Field(default=None, ge=1, le=31)
    payment_day: Optional[int] = Field(default=None, ge=1, le=31)
    interest_rate: Optional[float] = None
    monthly_payment: Optional[float] = None
    remaining_installments: Optional[int] = None
    next_payment_date: Optional[date] = None
    fund_code: Optional[str] = None
    lot_count: Optional[float] = None
    cost_per_lot: Optional[float] = None
    current_price: Optional[float] = None
    is_emanet: Optional[bool] = None


class AccountRead(AccountBase, TimestampedSchema):
    id: int
    user_id: int
    last_price_update: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# === RECURRING INCOME ===

class RecurringIncomeBase(BaseModel):
    name: str
    amount: float
    day_of_month: int = Field(ge=1, le=31)
    is_active: bool = True
    notes: Optional[str] = None


class RecurringIncomeCreate(RecurringIncomeBase):
    pass


class RecurringIncomeUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class RecurringIncomeRead(RecurringIncomeBase, TimestampedSchema):
    id: int
    user_id: int


# === TRANSACTION ===

class TransactionBase(BaseModel):
    account_id: Optional[int] = None
    transaction_type: Literal["income", "expense", "transfer"]
    amount: float
    category: Optional[str] = None
    description: Optional[str] = None
    transaction_date: date = Field(default_factory=date.today)
    is_card_expense: bool = False


class TransactionCreate(TransactionBase):
    pass


class TransactionRead(TransactionBase, TimestampedSchema):
    id: int
    user_id: int


# === PERSONAL DEBT ===

class PersonalDebtBase(BaseModel):
    counterparty: str
    direction: Literal["receivable", "payable"]
    amount: float
    description: Optional[str] = None
    due_date: Optional[date] = None
    is_paid: bool = False
    paid_date: Optional[date] = None


class PersonalDebtCreate(PersonalDebtBase):
    pass


class PersonalDebtUpdate(BaseModel):
    amount: Optional[float] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    is_paid: Optional[bool] = None
    paid_date: Optional[date] = None


class PersonalDebtRead(PersonalDebtBase, TimestampedSchema):
    id: int
    user_id: int


# === MASTER CHECKPOINT ===

class MasterCheckpointBase(BaseModel):
    title: str
    description: str
    checkpoint_type: Literal["red_line", "strategy", "rule", "context"]
    priority: int = Field(default=2, ge=1, le=3)
    is_active: bool = True


class MasterCheckpointCreate(MasterCheckpointBase):
    pass


class MasterCheckpointRead(MasterCheckpointBase, TimestampedSchema):
    id: int
    user_id: int


# === COACH ===

class CoachMessageRequest(BaseModel):
    """Kullanıcı koçtan ne istiyor."""
    message: str
    include_cockpit: bool = True  # Sistem prompta cockpit verisi enjekte edilsin mi


class ProposedAction(BaseModel):
    """Koçun önerdiği, onay bekleyen aksiyon."""
    action_id: int
    action_type: str
    summary: str
    payload: dict


class CoachMessageResponse(BaseModel):
    """Koçun cevabı."""
    reply: str
    proposed_actions: List[ProposedAction] = []
    cockpit_snapshot: Optional[dict] = None


class CoachMemoryRead(TimestampedSchema):
    id: int
    role: str
    content: str
    timestamp: datetime


# === PENDING ACTION ===

class PendingActionRead(TimestampedSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    action_type: str
    payload: str  # JSON string
    summary: str
    status: Literal["pending", "approved", "rejected", "executed", "failed"]
    error_message: Optional[str] = None
    resolved_at: Optional[datetime] = None


class ActionDecision(BaseModel):
    """Kullanıcının aksiyon hakkındaki kararı."""
    decision: Literal["approve", "reject"]
    reason: Optional[str] = None


# === COCKPIT (RULES ENGINE ÇIKTISI) ===

class CockpitSnapshot(BaseModel):
    """Rules Engine'in ürettiği günlük durum özeti."""
    date: str
    statu: str

    # Ana göstergeler
    nakit_kasa: float
    kart_borcu: float
    reel_butce: float
    net_deger: float
    emanet_kasa: float

    # Bugün
    daily_limit: float
    days_remaining: int

    # ZikZak
    carried_forward: float
    today_target: float

    # Detaylar
    accounts: List[dict]
    upcoming_payments: List[dict]
    upcoming_receivables: List[dict]
    alerts: List[dict]
    investment_pnl: List[dict]


# ============================================================
# H2G5 GOAL ENGINE (ADR-024)
# ============================================================

class GoalCreate(BaseModel):
    goal_type: Literal["debt_freedom", "cash_target"]
    title: str = Field(..., min_length=1, max_length=200)
    target_amount: Decimal = Field(..., gt=0)
    target_date: Optional[date] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    target_amount: Optional[Decimal] = Field(None, gt=0)
    target_date: Optional[date] = None
    # BUG #063 fix (SH-002): "achieved" çıkarıldı. achieved geçişi SADECE
    # goal_engine.refresh_goal'da (gerçek katkı >= target ise) olur; kullanıcı PATCH ile
    # hiç katkı yapmadan "sanal başarı" işaretleyemez ("Rules Engine karar verir" ilkesi).
    status: Optional[Literal["active", "paused", "abandoned"]] = None


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    goal_type: str
    title: str
    target_amount: Decimal
    baseline_amount: Optional[Decimal] = None
    target_date: Optional[date]
    status: str
    current_amount: Decimal
    progress_percent: Decimal
    projected_completion_date: Optional[date]
    last_refreshed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    achieved_at: Optional[datetime]


class GoalAllocationCreate(BaseModel):
    transaction_id: int
    amount: Decimal  # pozitif=katkı, negatif=çekim


class GoalAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    transaction_id: int
    amount: Decimal
    source: str
    rule_id: Optional[int]
    created_at: datetime


class GoalRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    priority: int = 0
    criteria: dict
    allocation_type: Literal["full", "percent", "fixed"]
    allocation_value: Optional[Decimal] = Field(None, ge=0)
    is_active: bool = True

    @field_validator("allocation_value")
    @classmethod
    def value_required_for_percent_or_fixed(cls, v, info):
        atype = info.data.get("allocation_type")
        if atype in ("percent", "fixed") and v is None:
            raise ValueError(f"{atype} allocation requires allocation_value")
        if atype == "percent" and v is not None and (v <= 0 or v > 100):
            raise ValueError("percent must be in (0, 100]")
        return v


class GoalRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    priority: Optional[int] = None
    criteria: Optional[dict] = None
    allocation_type: Optional[Literal["full", "percent", "fixed"]] = None
    allocation_value: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None


class GoalRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    name: str
    priority: int
    criteria: dict
    allocation_type: str
    allocation_value: Optional[Decimal]
    is_active: bool
    created_at: datetime