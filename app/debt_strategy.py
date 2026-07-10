"""
Debt Strategy Engine - Snowball + Avalanche payoff calculator.

Sektor standardi iki strateji:
- Snowball (Dave Ramsey): kucuk bakiyeden buyuge, davranissal motivasyon
- Avalanche (matematik): yuksek faizden dusuge, toplam maliyet minimum

Algoritma 100% deterministik. LLM yok. Pure Python.

ADR-001 uygulamasi: algoritma karar verir (matematik sektor standardi),
kullanici hangi stratejiyle gidecegini secer, AI sadece aciklar.

Mimari notlar:
- Mevcut Account.monthly_payment minimum varsayilir
- 'extra_monthly' kullanici girdisi, ekstra para tum minimumlar uzerine eklenir
- Bir borc bitince freed minimum + extra sonraki borca kayar (rollover)
- Faiz oraninin AYLIK oldugu varsayilir (Account.interest_rate, TR konvansiyonu)
- Kart icin minimum payment %25 bakiye (TR asgari odeme orani)
- Kredi icin minimum = Account.monthly_payment
- Faiz orani yoksa: kart default %4,25/ay, kredi skip (faizsiz simule edilir)
- Max simulasyon: 600 ay (50 yil) - sonsuz dongu koruma
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountType


# ============================================================
# SABITLER
# ============================================================

DEFAULT_CARD_INTEREST_MONTHLY = 4.25  # TCMB tavan TR (%/ay)
MIN_CARD_PAYMENT_RATIO = 0.25         # Kart asgari odeme orani (TR)
MAX_MONTHS = 600                      # Sonsuz dongu koruma


# ============================================================
# VERI YAPILARI
# ============================================================

@dataclass
class DebtItem:
    """Strateji icin normalize edilmis borc."""
    account_id: int
    name: str
    account_type: str              # 'credit_card' | 'loan'
    balance: float
    interest_rate_monthly: float   # %/ay (0.0 - 100.0 araliginda)
    min_payment: float             # Aylik minimum odeme


@dataclass
class MonthSnapshot:
    """Bir ayin simulasyonu."""
    month_index: int
    debt_balances: Dict[int, float]
    paid_this_month: Dict[int, float]
    interest_this_month: Dict[int, float]
    payoff_events: List[int]       # Bu ayda biten borc account_id'leri


@dataclass
class StrategyResult:
    """Tek stratejinin tam sonucu."""
    strategy: str                  # 'snowball' | 'avalanche'
    order: List[int]               # Account ID sirasinda (oncelik)
    months_to_freedom: int
    total_interest_paid: float
    total_paid: float
    payoff_date: Optional[date]
    schedule: List[MonthSnapshot]
    debt_payoff_months: Dict[int, int]  # {account_id: ay_sayisi}


# ============================================================
# YARDIMCI FONKSIYONLAR
# ============================================================

def collect_debts(db: Session, user_id: int) -> List[DebtItem]:
    """DB'den borc hesaplarini cek, DebtItem listesi don."""
    stmt = select(Account).where(
        Account.user_id == user_id,
        Account.account_type.in_([AccountType.credit_card, AccountType.loan]),
        Account.balance > 0,
    )
    accounts = db.execute(stmt).scalars().all()

    items: List[DebtItem] = []
    for a in accounts:
        is_card = a.account_type == AccountType.credit_card

        rate = a.interest_rate
        if rate is None or rate <= 0:
            rate = DEFAULT_CARD_INTEREST_MONTHLY if is_card else 0.0

        if is_card:
            min_pay = max(float(a.balance) * MIN_CARD_PAYMENT_RATIO, 50.0)
        else:
            min_pay = float(a.monthly_payment or 0.0)
            if min_pay <= 0:
                if a.remaining_installments and a.remaining_installments > 0:
                    min_pay = float(a.balance) / a.remaining_installments
                else:
                    min_pay = float(a.balance) * 0.05

        items.append(DebtItem(
            account_id=a.id,
            name=a.name,
            account_type=a.account_type.value,
            balance=float(a.balance),
            interest_rate_monthly=float(rate),
            min_payment=float(min_pay),
        ))

    return items


def _simulate(
    debts: List[DebtItem],
    priority_order: List[int],
    extra_monthly: float,
) -> StrategyResult:
    """
    Verilen oncelik sirasi + ekstra para ile ay-ay simulasyon.
    Snowball/Avalanche ortak motoru - sadece priority_order farkli.
    """
    if not debts:
        return StrategyResult(
            strategy='', order=[], months_to_freedom=0,
            total_interest_paid=0.0, total_paid=0.0,
            payoff_date=None, schedule=[], debt_payoff_months={},
        )

    state: Dict[int, float] = {d.account_id: d.balance for d in debts}
    debt_by_id: Dict[int, DebtItem] = {d.account_id: d for d in debts}

    total_interest = 0.0
    total_paid = 0.0
    schedule: List[MonthSnapshot] = []
    debt_payoff_months: Dict[int, int] = {}
    month = 0

    while any(b > 0.01 for b in state.values()) and month < MAX_MONTHS:
        month += 1
        snapshot_interest: Dict[int, float] = {}
        snapshot_paid: Dict[int, float] = {}
        snapshot_events: List[int] = []

        # 1. Faiz tahakkuk
        for aid, bal in list(state.items()):
            if bal <= 0.01:
                continue
            d = debt_by_id[aid]
            interest = bal * (d.interest_rate_monthly / 100.0)
            state[aid] = bal + interest
            total_interest += interest
            snapshot_interest[aid] = interest

        # 2. Minimum odemeleri yap
        available_extra = extra_monthly
        for aid in priority_order:
            if state[aid] <= 0.01:
                continue
            d = debt_by_id[aid]
            # BUG #079 fix (P0-3): kart asgari ödemesi her ay GÜNCEL bakiyeden hesaplanır
            # (azalır). Eskiden collect_debts'te başlangıç bakiyesinden hesaplanan SABİT
            # min_payment kullanılıyordu → kart gerçekte olduğundan hızlı kapanıyor,
            # snowball/avalanche payoff ay sayısı sistemli iyimser çıkıyordu.
            if d.account_type == 'credit_card':
                base_min = max(state[aid] * MIN_CARD_PAYMENT_RATIO, 50.0)
            else:
                base_min = d.min_payment  # kredi: sabit taksit
            min_pay = min(base_min, state[aid])  # Bakiyeden fazla ödeme yok
            state[aid] -= min_pay
            total_paid += min_pay
            snapshot_paid[aid] = min_pay

            if state[aid] < 0.01:
                refund = abs(state[aid])
                state[aid] = 0.0
                available_extra += refund
                snapshot_events.append(aid)
                if aid not in debt_payoff_months:
                    debt_payoff_months[aid] = month

        # 3. Ekstra parayi oncelik sirasinda kalan ilk borca uygula (rollover)
        for aid in priority_order:
            if available_extra <= 0.01:
                break
            if state[aid] <= 0.01:
                continue
            pay = min(available_extra, state[aid])
            state[aid] -= pay
            available_extra -= pay
            total_paid += pay
            snapshot_paid[aid] = snapshot_paid.get(aid, 0.0) + pay

            if state[aid] < 0.01:
                state[aid] = 0.0
                if aid not in snapshot_events:
                    snapshot_events.append(aid)
                if aid not in debt_payoff_months:
                    debt_payoff_months[aid] = month

        schedule.append(MonthSnapshot(
            month_index=month,
            debt_balances={aid: round(b, 2) for aid, b in state.items()},
            paid_this_month={aid: round(p, 2) for aid, p in snapshot_paid.items()},
            interest_this_month={aid: round(i, 2) for aid, i in snapshot_interest.items()},
            payoff_events=list(snapshot_events),
        ))

        # 4. Snowball/Avalanche rollover: biten borclarin minimum'u sonraki ay extra'ya eklenir
        for aid in snapshot_events:
            extra_monthly += debt_by_id[aid].min_payment

    payoff = date.today() + timedelta(days=month * 30)

    return StrategyResult(
        strategy='',
        order=priority_order,
        months_to_freedom=month,
        total_interest_paid=round(total_interest, 2),
        total_paid=round(total_paid, 2),
        payoff_date=payoff,
        schedule=schedule,
        debt_payoff_months=debt_payoff_months,
    )


# ============================================================
# STRATEJI ALGORITMALARI
# ============================================================

def calc_snowball(debts: List[DebtItem], extra_monthly: float = 0.0) -> StrategyResult:
    """Snowball: bakiye kucukten buyuge."""
    order = sorted(debts, key=lambda d: d.balance)
    result = _simulate(debts, [d.account_id for d in order], extra_monthly)
    result.strategy = 'snowball'
    return result


def calc_avalanche(debts: List[DebtItem], extra_monthly: float = 0.0) -> StrategyResult:
    """Avalanche: faiz orani yuksekten dusuge."""
    order = sorted(debts, key=lambda d: -d.interest_rate_monthly)
    result = _simulate(debts, [d.account_id for d in order], extra_monthly)
    result.strategy = 'avalanche'
    return result


def compare_strategies(
    db: Session,
    user_id: int,
    extra_monthly: float = 0.0,
) -> dict:
    """
    Iki stratejiyi yan yana hesapla, karsilastirma sonucu don.

    Returns:
        {debts, snowball, avalanche, comparison: {interest_saved, months_difference, note}}
    """
    debts = collect_debts(db, user_id)

    if not debts:
        return {
            'debts': [],
            'snowball': None,
            'avalanche': None,
            'comparison': {
                'interest_saved_with_avalanche': 0.0,
                'months_difference': 0,
                'recommendation_note': 'Aktif borc yok.',
            }
        }

    snowball = calc_snowball(debts, extra_monthly)
    avalanche = calc_avalanche(debts, extra_monthly)

    saved = snowball.total_interest_paid - avalanche.total_interest_paid
    months_diff = snowball.months_to_freedom - avalanche.months_to_freedom

    if abs(saved) < 50:
        note = 'Iki strateji neredeyse ayni sonuc verir. Davranissal tercih daha onemli.'
    elif saved > 0:
        note = (
            f'Avalanche {saved:.0f} TL tasarruf eder ve {abs(months_diff)} ay daha '
            f'hizli biter. Snowball motivasyon icin tercih edilir.'
        )
    else:
        note = (
            f'Snowball {abs(saved):.0f} TL tasarruf eder — cunku kucuk borc yuksek '
            f'faizli. Iki yontem de iyi secim.'
        )

    return {
        'debts': [
            {
                'account_id': d.account_id,
                'name': d.name,
                'account_type': d.account_type,
                'balance': d.balance,
                'interest_rate_monthly': d.interest_rate_monthly,
                'min_payment': d.min_payment,
            }
            for d in debts
        ],
        'snowball': _result_to_dict(snowball),
        'avalanche': _result_to_dict(avalanche),
        'comparison': {
            'interest_saved_with_avalanche': round(saved, 2),
            'months_difference': months_diff,
            'recommendation_note': note,
        }
    }


def _result_to_dict(r: StrategyResult) -> dict:
    """StrategyResult -> JSON-serializeable dict (schedule haric)."""
    return {
        'strategy': r.strategy,
        'order': r.order,
        'months_to_freedom': r.months_to_freedom,
        'total_interest_paid': r.total_interest_paid,
        'total_paid': r.total_paid,
        'payoff_date': r.payoff_date.isoformat() if r.payoff_date else None,
        'debt_payoff_months': r.debt_payoff_months,
    }
