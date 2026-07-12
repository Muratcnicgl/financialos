"""
Cashflow forecast motoru — H2G1.

Matematiksel hesaplar burada (Rules Engine prensibi).
LLM bu modülü çağırmaz; yalnızca router üzerinden kullanılır.

Para birimi: TL (float), mevcut model şemasıyla tutarlı.
Timezone: date.today() — lokal sistem saati (UTC+3 Istanbul).
Kapsam dışı (Wave-3):
  - Yatırım hesapları (multi-asset ayrı design)
  - Kredi kartı taksit döngüsü (MC3 Ziraat cycle ayrı design)
  - One-off scheduled tx (Transaction.due_date yok)

BUG #058 fix: Kredi taksitleri artık "expenses" chip altında tam olarak genişletiliyor.
  Eski _loan_payments_in_range sadece next_payment_date'e bakıyordu (tek occurrence).
  Yeni _expand_loan_payments remaining_installments kadar aylık ileri gider.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    Account, AccountType,
    PersonalDebt, DebtDirection,
    RecurringIncome, RecurringExpense,
)


# ============================================================
# VERİ YAPILARI
# ============================================================

class ForecastEvent:
    """Tek bir nakit akışı olayı."""
    __slots__ = ("date", "amount", "label", "source_type", "source_id")

    def __init__(
        self, d: date, amount: float, label: str, source_type: str, source_id: int
    ):
        self.date = d
        self.amount = amount         # pozitif = giriş, negatif = çıkış (TL)
        self.label = label
        self.source_type = source_type  # income|recurring_expense|receivable|payable|loan
        self.source_id = source_id


class ForecastDay:
    """Tek takvim günü özeti."""
    __slots__ = (
        "date", "opening_balance", "closing_balance",
        "inflows", "outflows", "events", "crunch",
    )

    def __init__(self, d: date, opening: float):
        self.date = d
        self.opening_balance = round(opening, 2)
        self.closing_balance = opening
        self.inflows = 0.0
        self.outflows = 0.0
        self.events: list[ForecastEvent] = []
        self.crunch = False


# ============================================================
# YARDIMCI GENİŞLETİCİLER
# ============================================================

def _month_occurrences(start: date, end: date, day_of_month: int) -> list[date]:
    """start <= d <= end olan tüm aylık tekrar tarihlerini döner."""
    results = []
    cur = start.replace(day=1)
    while cur <= end:
        last = monthrange(cur.year, cur.month)[1]
        candidate = date(cur.year, cur.month, min(day_of_month, last))
        if start <= candidate <= end:
            results.append(candidate)
        cur = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    return results


def _expand_recurring_income(
    income: RecurringIncome, start: date, end: date
) -> list[ForecastEvent]:
    return [
        ForecastEvent(d, income.amount, income.name, "income", income.id)
        for d in _month_occurrences(start, end, income.day_of_month)
    ]


def _expand_recurring_expense(
    expense: RecurringExpense, start: date, end: date
) -> list[ForecastEvent]:
    return [
        ForecastEvent(d, -expense.amount, expense.name, "recurring_expense", expense.id)
        for d in _month_occurrences(start, end, expense.day_of_month)
    ]


def _personal_debts_in_range(
    db: Session,
    user_id: int,
    start: date,
    end: date,
    direction: DebtDirection,
) -> list[ForecastEvent]:
    source_type = "receivable" if direction == DebtDirection.receivable else "payable"
    rows = (
        db.query(PersonalDebt)
        .filter(
            PersonalDebt.user_id == user_id,
            PersonalDebt.direction == direction,
            PersonalDebt.is_paid == False,   # noqa: E712
            PersonalDebt.due_date.isnot(None),
            PersonalDebt.due_date >= start,
            PersonalDebt.due_date <= end,
        )
        .all()
    )
    events: list[ForecastEvent] = []
    for d in rows:
        label = d.counterparty + (f" — {d.description}" if d.description else "")
        amount = d.amount if direction == DebtDirection.receivable else -d.amount
        events.append(ForecastEvent(d.due_date, amount, label, source_type, d.id))
    return events


def _advance_month(d: date) -> date:
    """Bir ay ilerlet; ay sonu durumlarını monthrange ile kenetler."""
    next_month = d.month % 12 + 1
    next_year = d.year + (d.month // 12)
    last = monthrange(next_year, next_month)[1]
    return d.replace(year=next_year, month=next_month, day=min(d.day, last))


def _expand_loan_payments(
    account: Account, start: date, end: date
) -> list[ForecastEvent]:
    """BUG #058 fix: Kredi hesabının horizon içindeki tüm taksit occurrence'larını üretir.

    Account.next_payment_date'ten başlar, remaining_installments kadar aylık ilerler.
    Yalnızca [start, end] aralığındaki tarihler olay listesine eklenir.
    """
    if account.account_type != AccountType.loan:
        return []
    if not account.next_payment_date or not account.monthly_payment:
        return []
    remaining = account.remaining_installments or 0
    if remaining == 0:
        return []

    events: list[ForecastEvent] = []
    current = account.next_payment_date
    # RULE-016 fix: STALE (geçmiş) next_payment_date remaining'i BOŞA HARCAMASIN. Eskiden
    # geçmiş occurrence'lar (current >= start False) atlanıyor ama idx'i tüketiyordu → 4 taksit
    # kalan + 6 ay eski tarihli kredi forecast'ta 0 gelecek ödeme gösteriyordu (yükümlülük
    # HAFİFE görünüp crunch/safe-to-spend'i iyimser yapıyordu). Geçmiş-vadeliyi bugüne çek:
    # remaining taksit tümü gelecek yükümlülük olarak projelenir (aya ötelenmez, kaybolmaz).
    if current < start:
        current = start
    # RULE-017 fix: ANCHOR gün (ayın sabit günü) ile ilerle — _advance_month(current) her ay
    # current.day'i clamp'leyip taşıyordu → 31'inde taksit Şubat'ta 28'e düşünce Mart'ta 31'e
    # DÖNMÜYOR (sürüklenme). Anchor'la min(anchor, ay_sonu) → Mart yine 31. _month_occurrences
    # (recurring) zaten doğru; loan yolu bu düzeltmeyle hizalandı.
    anchor_day = current.day
    idx = 0
    while current <= end and idx < remaining:
        events.append(ForecastEvent(
            current,
            -(account.monthly_payment),
            f"{account.name} taksiti",
            "loan_payment",
            account.id,
        ))
        y = current.year + (current.month == 12)
        m = current.month % 12 + 1
        current = date(y, m, min(anchor_day, monthrange(y, m)[1]))
        idx += 1
    return events


# ============================================================
# SANKEY
# ============================================================

def _build_sankey(events: list[ForecastEvent]) -> dict:
    """
    Kaynak→Nakit→Hedef Sankey yapısı döner.
    Sol: gelir kaynakları, Merkez: "Nakit", Sağ: gider hedefleri.
    """
    CASH_NODE = "Nakit"
    source_totals: dict[str, float] = {}
    sink_totals: dict[str, float] = {}

    for ev in events:
        if ev.amount > 0:
            source_totals[ev.label] = source_totals.get(ev.label, 0.0) + ev.amount
        elif ev.amount < 0:
            sink_totals[ev.label] = sink_totals.get(ev.label, 0.0) + abs(ev.amount)

    if not source_totals and not sink_totals:
        return {"nodes": [], "links": []}

    nodes: list[dict] = []
    node_index: dict[str, int] = {}

    def _add_node(name: str, ntype: str) -> int:
        if name not in node_index:
            idx = len(nodes)
            node_index[name] = idx
            nodes.append({"id": idx, "name": name, "type": ntype})
        return node_index[name]

    cash_idx = _add_node(CASH_NODE, "cash")

    links: list[dict] = []
    for label, total in source_totals.items():
        src_idx = _add_node(label, "income")
        links.append({
            "source": src_idx, "target": cash_idx,
            "value": round(total, 2), "label": label,
        })
    for label, total in sink_totals.items():
        sink_idx = _add_node(label, "expense")
        links.append({
            "source": cash_idx, "target": sink_idx,
            "value": round(total, 2), "label": label,
        })

    return {"nodes": nodes, "links": links}


# ============================================================
# ANA FORECAST FONKSİYONU
# ============================================================

VALID_INCLUDE = {"incomes", "expenses", "receivables", "payables"}


def generate_forecast(
    db: Session,
    user_id: int,
    horizon_days: int = 60,
    account_id: Optional[int] = None,
    include: Optional[set[str]] = None,
    crunch_threshold: float = 0.0,
    today: Optional[date] = None,
) -> dict:
    """
    Nakit akışı tahmini üretir.

    Parametreler
    ------------
    db               : SQLAlchemy session
    user_id          : hedef kullanıcı
    horizon_days     : kaç günlük tahmin (varsayılan 60)
    account_id       : None = tüm nakit hesaplar; int = tek hesap
    include          : filtre chipsleri; None = hepsi dahil
    crunch_threshold : bu tutarın (TL) altına düşen günler crunch=True
    today            : projeksiyon başlangıcı (None = date.today()). Enjekte edilebilir —
                       generate_cockpit'in `today`'siyle TUTARLILIK + deterministik test için.

    Dönüş: {horizon_days, start_date, end_date, currency,
             days: [ForecastDay], summary: dict, sankey: dict}
    """
    if include is None:
        include = VALID_INCLUDE.copy()

    today = today or date.today()
    end = today + timedelta(days=horizon_days - 1)

    # --- Başlangıç bakiyesi: nakit hesaplar ---
    # BİLİNEN SINIRLAMA (denetim, BUG #107): account_id verilirse SADECE açılış bakiyesi ve
    # (aşağıda) recurring gider bu hesaba göre daraltılır; gelir/kredi taksiti/alacak/borç
    # RecurringIncome/PersonalDebt'te account_id olmadığı için GLOBAL kalır. Yani tek-hesap
    # projeksiyonu "bu hesap tüm nakit akışının merkezi" varsayar (izole hesap DEĞİL).
    # Şu an hiçbir UI çağrısı account_id GEÇMİYOR (hep agregat mod) → yol pratikte kullanılmıyor.
    # İzole-hesap semantiği ürün kararı gerektirir; varsayımla davranış değiştirilmedi.
    cash_q = db.query(Account).filter(
        Account.user_id == user_id,
        Account.account_type == AccountType.cash,
    )
    if account_id is not None:
        cash_q = cash_q.filter(Account.id == account_id)
    opening_balance = sum(acc.balance for acc in cash_q.all())

    # --- Olayları topla ---
    all_events: list[ForecastEvent] = []

    if "incomes" in include:
        for inc in db.query(RecurringIncome).filter(
            RecurringIncome.user_id == user_id,
            RecurringIncome.is_active == True,  # noqa: E712
        ).all():
            all_events.extend(_expand_recurring_income(inc, today, end))

    if "expenses" in include:
        exp_q = db.query(RecurringExpense).filter(
            RecurringExpense.user_id == user_id,
            RecurringExpense.is_active == True,  # noqa: E712
        )
        if account_id is not None:
            exp_q = exp_q.filter(RecurringExpense.account_id == account_id)
        for exp in exp_q.all():
            all_events.extend(_expand_recurring_expense(exp, today, end))
        # BUG #058 fix: kredi taksitleri sabit gider sınıfında, "expenses" chip'i ile dahil edilir
        for loan in db.query(Account).filter(
            Account.user_id == user_id,
            Account.account_type == AccountType.loan,
        ).all():
            all_events.extend(_expand_loan_payments(loan, today, end))

    if "receivables" in include:
        all_events.extend(
            _personal_debts_in_range(db, user_id, today, end, DebtDirection.receivable)
        )

    if "payables" in include:
        all_events.extend(
            _personal_debts_in_range(db, user_id, today, end, DebtDirection.payable)
        )

    # --- Tarihe göre grupla ---
    events_by_date: dict[date, list[ForecastEvent]] = {}
    for ev in all_events:
        events_by_date.setdefault(ev.date, []).append(ev)

    # --- Günlük tablo ---
    days: list[ForecastDay] = []
    balance = opening_balance
    lowest_balance = balance
    lowest_date = today
    crunch_dates: list[str] = []

    for i in range(horizon_days):
        d = today + timedelta(days=i)
        day = ForecastDay(d, balance)

        for ev in sorted(events_by_date.get(d, []), key=lambda e: -abs(e.amount)):
            day.events.append(ev)
            if ev.amount >= 0:
                day.inflows += ev.amount
            else:
                day.outflows += ev.amount

        balance = balance + day.inflows + day.outflows
        day.closing_balance = round(balance, 2)
        day.inflows = round(day.inflows, 2)
        day.outflows = round(day.outflows, 2)

        if balance < crunch_threshold:
            day.crunch = True
            crunch_dates.append(d.isoformat())

        if balance < lowest_balance:
            lowest_balance = balance
            lowest_date = d

        days.append(day)

    total_receivable = sum(ev.amount for ev in all_events if ev.amount > 0)
    total_payable = sum(ev.amount for ev in all_events if ev.amount < 0)

    return {
        "horizon_days": horizon_days,
        "start_date": today.isoformat(),
        "end_date": end.isoformat(),
        "currency": "TRY",
        "days": days,
        "summary": {
            "lowest_balance": round(lowest_balance, 2),
            "lowest_date": lowest_date.isoformat(),
            "total_receivable": round(total_receivable, 2),
            "total_payable": round(total_payable, 2),
            "net_flow": round(total_receivable + total_payable, 2),
            "crunch_count": len(crunch_dates),
            "crunch_dates": crunch_dates,
            "opening_balance": round(opening_balance, 2),
        },
        "sankey": _build_sankey(all_events),
    }
