"""
FinancialOS Senaryo Motoru — "Eger X yaparsam ne olur?"

Mimari prensip:
- Gercek DB'ye HIC dokunmaz. Tum hesaplar/borclar/gelirler RAM'e kopyalanir.
- Aksiyon kopyaya uygulanir, sonra T+gun kadar projeksiyon yapilir.
- Projeksiyon: dusulen kredi taksitleri + gelen maaslar + Efe alacaklari + kart son odemeleri.
- Cikti: T+0, T+30, T+60, T+90 snapshot'lari + delta tablosu.

Bu modul iki yerden cagrilir:
1. /api/simulate endpoint'i (kullanici ne-olur sorgusu)
2. coach.py'deki get_simulation araci (LLM kendi senaryosunu kursun)

Bagimsizlik: action_executor.py veya rules_engine.py'yi import etmez. Bu sayede
gercek DB'ye sizinti riski yok. Mantigi burada bagimsiz ama tutarli sekilde yazilmistir.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from calendar import monthrange
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import (
    Account, AccountType, RecurringIncome,
    PersonalDebt, DebtDirection,
)


# ============================================================
# 1. RAM SNAPSHOT — gercek DB'nin guvenli kopyasi
# ============================================================

@dataclass
class AccountSnap:
    id: int
    name: str
    account_type: str
    balance: float
    is_emanet: bool = False
    credit_limit: Optional[float] = None
    statement_day: Optional[int] = None
    payment_day: Optional[int] = None
    monthly_payment: Optional[float] = None
    remaining_installments: Optional[int] = None
    next_payment_date: Optional[date] = None
    fund_code: Optional[str] = None
    lot_count: Optional[float] = None
    cost_per_lot: Optional[float] = None
    current_price: Optional[float] = None


@dataclass
class IncomeSnap:
    id: int
    name: str
    amount: float
    day_of_month: int
    is_active: bool = True


@dataclass
class DebtSnap:
    id: int
    counterparty: str
    direction: str  # "payable" | "receivable"
    amount: float
    due_date: Optional[date]
    paid_date: Optional[date]


@dataclass
class WorldSnap:
    """Belirli bir andaki finansal evren. Mutable — projeksiyon ilerletir."""
    as_of: date
    accounts: List[AccountSnap]
    incomes: List[IncomeSnap]
    debts: List[DebtSnap]
    event_log: List[str] = field(default_factory=list)

    # ---- erisim yardimcilari ----
    def acc(self, account_id: int) -> Optional[AccountSnap]:
        for a in self.accounts:
            if a.id == account_id:
                return a
        return None

    def cash_total(self) -> float:
        return sum(a.balance for a in self.accounts if a.account_type == "cash")

    def card_debt_total(self) -> float:
        return sum(a.balance for a in self.accounts if a.account_type == "credit_card")

    def loan_debt_total(self) -> float:
        return sum(a.balance for a in self.accounts if a.account_type == "loan")

    def investment_value(self, include_emanet: bool = False) -> float:
        return sum(
            a.balance for a in self.accounts
            if a.account_type == "investment" and (include_emanet or not a.is_emanet)
        )

    def emanet_value(self) -> float:
        return sum(
            a.balance for a in self.accounts
            if a.account_type == "investment" and a.is_emanet
        )

    def net_worth(self) -> float:
        """Emanet HARIC net deger."""
        return (
            self.cash_total()
            + self.investment_value(include_emanet=False)
            - self.card_debt_total()
            - self.loan_debt_total()
        )


# ============================================================
# 2. SNAPSHOT YUKLEYICI — gercek DB'den RAM'e kopyala
# ============================================================

def _load_world(db: Session, user_id: int, as_of: date) -> WorldSnap:
    """DB'den hicbir nesneye baglanmadan dataclass kopyasi cikar."""
    accs_db = db.query(Account).filter(Account.user_id == user_id).all()
    accounts = [
        AccountSnap(
            id=a.id,
            name=a.name,
            account_type=a.account_type.value,
            balance=float(a.balance or 0.0),
            is_emanet=bool(a.is_emanet),
            credit_limit=float(a.credit_limit) if a.credit_limit else None,
            statement_day=a.statement_day,
            payment_day=a.payment_day,
            monthly_payment=float(a.monthly_payment) if a.monthly_payment else None,
            remaining_installments=a.remaining_installments,
            next_payment_date=a.next_payment_date,
            fund_code=a.fund_code,
            lot_count=float(a.lot_count) if a.lot_count else None,
            cost_per_lot=float(a.cost_per_lot) if a.cost_per_lot else None,
            current_price=float(a.current_price) if a.current_price else None,
        )
        for a in accs_db
    ]

    incs_db = (
        db.query(RecurringIncome)
        .filter(RecurringIncome.user_id == user_id)
        .all()
    )
    incomes = [
        IncomeSnap(
            id=i.id,
            name=i.name,
            amount=float(i.amount or 0.0),
            day_of_month=int(i.day_of_month or 1),
            is_active=bool(i.is_active),
        )
        for i in incs_db
    ]

    dbts_db = (
        db.query(PersonalDebt)
        .filter(PersonalDebt.user_id == user_id)
        .all()
    )
    debts = [
        DebtSnap(
            id=d.id,
            counterparty=d.counterparty,
            direction=d.direction.value,
            amount=float(d.amount or 0.0),
            due_date=d.due_date,
            paid_date=d.paid_date,
        )
        for d in dbts_db
    ]

    return WorldSnap(as_of=as_of, accounts=accounts, incomes=incomes, debts=debts)


# ============================================================
# 3. AKSIYON UYGULAMA — RAM uzerinde, gercek DB'ye HIC dokunmadan
# ============================================================

def _find_default_cash_account(world: WorldSnap) -> Optional[AccountSnap]:
    for a in world.accounts:
        if a.account_type == "cash":
            return a
    return None


def _apply_action(world: WorldSnap, action_type: str, payload: Dict) -> Tuple[bool, str]:
    """Aksiyonu RAM'e uygular. (basarili, mesaj) doner."""
    try:
        if action_type == "sell_investment":
            inv = world.acc(payload["investment_id"])
            if not inv:
                return False, f"Yatirim hesabi bulunamadi (id={payload['investment_id']})"
            if inv.is_emanet:
                return False, f"Emanet hesabi (MC1) — satis YASAK: {inv.name}"
            lots = float(payload["lots_to_sell"])
            if lots <= 0 or lots > (inv.lot_count or 0):
                return False, f"Gecersiz lot sayisi: {lots} (mevcut {inv.lot_count})"

            price = float(payload.get("actual_price") or inv.current_price or 0.0)
            gross = lots * price
            cost = lots * (inv.cost_per_lot or 0.0)
            profit = gross - cost
            withholding = max(0.0, profit) * 0.175  # %17.5 stopaj
            net_to_account = gross - withholding

            # Yatirim hesabini kucult
            inv.lot_count = (inv.lot_count or 0) - lots
            inv.balance = (inv.lot_count or 0) * (inv.current_price or 0)

            # Nakdi hedef hesaba ekle
            cash_id = payload.get("credit_to_account_id")
            target = world.acc(cash_id) if cash_id else _find_default_cash_account(world)
            if not target:
                return False, "Nakit hesabi bulunamadi"
            target.balance += net_to_account
            world.event_log.append(
                f"[T+0] SATIS: {lots} lot {inv.fund_code} @ {price:.2f} TL "
                f"= {gross:,.2f} brut, stopaj {withholding:,.2f}, "
                f"net {net_to_account:,.2f} TL -> {target.name}"
            )
            return True, "ok"

        if action_type == "add_transaction":
            ttype = payload.get("transaction_type", "expense")
            amount = float(payload["amount"])
            account_id = payload.get("account_id")
            target = world.acc(account_id) if account_id else _find_default_cash_account(world)
            if not target:
                return False, "Hedef hesap bulunamadi"

            if ttype not in ("income", "expense", "transfer"):
                return False, f"Bilinmeyen islem tipi: {ttype}"
            # BUG #080 fix (P0-8/SE-002): gerçek executor bakiyeyi SADECE auto_update_balance=True
            # iken günceller (action_executor:504) ve transfer'de HİÇ değiştirmez. Simülasyon
            # eskiden koşulsuz + transfer'de de değiştiriyordu → gerçekte bakiyeyi değiştirmeyecek
            # bir işlemi bakiye değişimi olarak ön-izleyip yanlış karar desteği veriyordu.
            if payload.get("auto_update_balance") and account_id:
                if ttype == "income":
                    target.balance += amount
                elif ttype == "expense":
                    if target.account_type == "credit_card":
                        target.balance += amount  # kart borcu artar
                    else:
                        target.balance -= amount  # nakit hesap azalir
                # transfer: executor bakiye değiştirmiyor → simülasyon da değiştirmez

            world.event_log.append(
                f"[T+0] ISLEM: {ttype} {amount:,.2f} TL -> {target.name} "
                f"({payload.get('category', '')})"
            )
            return True, "ok"

        if action_type == "update_account_balance":
            target = world.acc(payload["account_id"])
            if not target:
                return False, f"Hesap bulunamadi: {payload['account_id']}"
            old = target.balance
            target.balance = float(payload["new_balance"])
            world.event_log.append(
                f"[T+0] BAKIYE: {target.name} {old:,.2f} -> {target.balance:,.2f} TL"
            )
            return True, "ok"

        if action_type == "mark_debt_paid":
            d = next((x for x in world.debts if x.id == payload["debt_id"]), None)
            if not d:
                return False, f"Borc/alacak bulunamadi: {payload['debt_id']}"
            cash = _find_default_cash_account(world)
            if cash:
                if d.direction == "receivable":
                    cash.balance += d.amount
                else:
                    cash.balance -= d.amount
            d.paid_date = world.as_of
            world.event_log.append(
                f"[T+0] BORC/ALACAK: {d.counterparty} {d.amount:,.2f} TL "
                f"({d.direction}) ODENDI"
            )
            return True, "ok"

        if action_type == "update_fund_price":
            target = world.acc(payload["account_id"])
            if not target:
                return False, "Hesap bulunamadi"
            target.current_price = float(payload["new_price"])
            target.balance = (target.lot_count or 0) * target.current_price
            world.event_log.append(
                f"[T+0] FIYAT: {target.name} -> {target.current_price:.2f} TL"
            )
            return True, "ok"

        return False, f"Simulasyon su aksiyon tipini destekemiyor: {action_type}"

    except KeyError as e:
        return False, f"Payload eksik alan: {e}"
    except Exception as e:
        return False, f"Aksiyon hatasi: {e}"


# ============================================================
# 4. PROJEKSIYON — zamani ileri al, dogal hareketleri yansit
# ============================================================

def _last_day_of_month(d: date) -> int:
    return monthrange(d.year, d.month)[1]


def _next_payment_in_window(
    next_pay: Optional[date], start: date, end: date
) -> List[date]:
    """Bir kredi taksiti start-end araliginda hangi tarihlerde duser? (aylik tekrar)"""
    if not next_pay:
        return []
    hits = []
    cursor = next_pay
    while cursor <= end:
        if cursor >= start:
            hits.append(cursor)
        # bir sonraki ay
        y, m = cursor.year, cursor.month + 1
        if m > 12:
            m = 1
            y += 1
        # ayni gun, ama o ayda gun yoksa son gunu kullan
        ldom = monthrange(y, m)[1]
        cursor = date(y, m, min(cursor.day, ldom))
    return hits


def _project_forward(world: WorldSnap, days: int) -> WorldSnap:
    """Mevcut dunyayi 'days' gun ileri al. RecurringIncome + kredi taksiti +
    Efe alacaklari + kart kesim/odeme dongusu hesaplanir.
    """
    start = world.as_of
    end = world.as_of + timedelta(days=days)

    # 1. Maas/duzenli gelir
    for inc in world.incomes:
        if not inc.is_active:
            continue
        cursor = start
        while cursor <= end:
            ldom = _last_day_of_month(cursor)
            day = min(inc.day_of_month, ldom)
            pay_date = date(cursor.year, cursor.month, day)
            if start <= pay_date <= end:
                cash = _find_default_cash_account(world)
                if cash:
                    cash.balance += inc.amount
                    world.event_log.append(
                        f"[{pay_date}] GELIR: {inc.name} +{inc.amount:,.2f} -> {cash.name}"
                    )
            # bir sonraki ay
            y, m = cursor.year, cursor.month + 1
            if m > 12:
                m = 1
                y += 1
            cursor = date(y, m, 1)

    # 2. Kredi taksitleri
    for a in world.accounts:
        if a.account_type != "loan":
            continue
        for pay_date in _next_payment_in_window(a.next_payment_date, start, end):
            if not a.monthly_payment:
                continue
            cash = _find_default_cash_account(world)
            if cash:
                cash.balance -= a.monthly_payment
            a.balance = max(0.0, a.balance - a.monthly_payment)
            if a.remaining_installments:
                a.remaining_installments = max(0, a.remaining_installments - 1)
            world.event_log.append(
                f"[{pay_date}] KREDI TAKSITI: {a.name} -{a.monthly_payment:,.2f} "
                f"(kalan borc {a.balance:,.2f}, taksit {a.remaining_installments})"
            )

    # 3. Efe & diger kisi alacaklari/borclari
    for d in world.debts:
        if d.paid_date:
            continue
        if not d.due_date:
            continue
        if not (start <= d.due_date <= end):
            continue
        cash = _find_default_cash_account(world)
        if cash:
            if d.direction == "receivable":
                cash.balance += d.amount
            else:
                cash.balance -= d.amount
        d.paid_date = d.due_date
        world.event_log.append(
            f"[{d.due_date}] {'TAHSILAT' if d.direction == 'receivable' else 'ODEME'}: "
            f"{d.counterparty} {d.amount:,.2f} TL"
        )

    # 4. Kart son odemesi (basit model: ay sonunda kart borcu nakitten dusulur)
    # Kullanici otomatik odeme yaptigi varsayimiyla. Cockpit'in mevcut mantigi
    # kart-son-odeme'yi 'upcoming_payment' olarak gosteriyor; biz simulasyonda
    # konservatif davranip kart bakiyesini OLDUGU gibi birakiyoruz (kullanici
    # ne odedigini secmek isterse 'mark_debt_paid' / 'update_account_balance'
    # ile manuel duser). Bu, asiri-iyi-tahmin riskini onler.

    world.as_of = end
    return world


# ============================================================
# 5. SNAPSHOT FORMATLAYICI — frontend ve LLM icin
# ============================================================

def _snapshot_to_dict(world: WorldSnap, label: str) -> Dict:
    return {
        "label": label,
        "as_of": world.as_of.isoformat(),
        "nakit_kasa": round(world.cash_total(), 2),
        "kart_borcu": round(world.card_debt_total(), 2),
        "kredi_borcu": round(world.loan_debt_total(), 2),
        "yatirim_deger": round(world.investment_value(False), 2),
        "emanet_kasa": round(world.emanet_value(), 2),
        "net_deger": round(world.net_worth(), 2),
        "accounts": [
            {
                "id": a.id,
                "ad": a.name,
                "tip": a.account_type,
                "bakiye": round(a.balance, 2),
                "is_emanet": a.is_emanet,
                "lot": a.lot_count,
                "fiyat": a.current_price,
                "kalan_taksit": a.remaining_installments,
            }
            for a in world.accounts
        ],
    }


def _delta(before: Dict, after: Dict) -> Dict:
    """Iki snapshot'in farkini cikar."""
    keys = ["nakit_kasa", "kart_borcu", "kredi_borcu", "yatirim_deger",
            "emanet_kasa", "net_deger"]
    return {k: round(after[k] - before[k], 2) for k in keys}


# ============================================================
# 6. ANA API — disaridan tek nokta cagri
# ============================================================

def simulate_action(
    db: Session,
    user_id: int,
    action_type: str,
    payload: Dict,
    horizons_days: Tuple[int, ...] = (0, 30, 60, 90),
    base_date: Optional[date] = None,
) -> Dict:
    """
    Hipotetik bir aksiyonu uygula ve gelecek snapshot'lari hesapla.

    Args:
        action_type: 'sell_investment' | 'add_transaction' | ...
        payload: Action_executor ile ayni format.
        horizons_days: Hangi gunler icin snapshot istenir. 0 = aksiyondan hemen sonra.
        base_date: Simulasyon baslangic tarihi (default: bugun).

    Returns:
        {
          'ok': bool,
          'message': str,
          'baseline': {...},        # aksiyon HIC yapilmadi senaryo (T+0)
          'snapshots': [             # aksiyon yapildi, ileri sariyor
            {label: 'T+0', ..., delta_vs_baseline: {...}},
            {label: 'T+30', ..., delta_vs_baseline: {...}},
            ...
          ],
          'event_log': [...],        # neler oldu, sira ile
          'comparison': {            # ozet karar tablosu
              'net_worth_change_30d': float,
              'cash_change_30d': float,
              'card_debt_change_30d': float,
          }
        }
    """
    today = base_date or date.today()

    # 1. AKSIYONSUZ (baseline) projeksiyon — referans icin
    baseline_world = _load_world(db, user_id, today)
    max_horizon = max(horizons_days) if horizons_days else 0
    if max_horizon > 0:
        _project_forward(baseline_world, max_horizon)
    baseline_snap = _snapshot_to_dict(baseline_world, f"BASELINE T+{max_horizon}")

    # 2. AKSIYONLU senaryo
    world = _load_world(db, user_id, today)
    ok, msg = _apply_action(world, action_type, payload)
    if not ok:
        return {
            "ok": False,
            "message": msg,
            "baseline": baseline_snap,
            "snapshots": [],
            "event_log": world.event_log,
            "comparison": {},
        }

    # 3. Her ufukta snapshot al
    snapshots: List[Dict] = []
    sorted_horizons = sorted(set(horizons_days))
    last_day = 0
    # T+0 snapshot'i: aksiyon uygulandi ama zaman ilerlemedi
    if 0 in sorted_horizons:
        snap0 = _snapshot_to_dict(world, "T+0")
        # Baseline ile farki: aksiyonun ANI etkisi
        base_t0 = _snapshot_to_dict(_load_world(db, user_id, today), "BASELINE T+0")
        snap0["delta_vs_baseline"] = _delta(base_t0, snap0)
        snapshots.append(snap0)
        sorted_horizons = [h for h in sorted_horizons if h != 0]

    # Sonraki ufuklar: aksiyondan sonra zamani ileri sar
    for h in sorted_horizons:
        delta_days = h - last_day
        _project_forward(world, delta_days)
        last_day = h
        snap = _snapshot_to_dict(world, f"T+{h}")

        # Karsilastirma: ayni horizon'daki BASELINE ile
        base_world_h = _load_world(db, user_id, today)
        if h > 0:
            _project_forward(base_world_h, h)
        base_snap = _snapshot_to_dict(base_world_h, f"BASELINE T+{h}")
        snap["delta_vs_baseline"] = _delta(base_snap, snap)
        snapshots.append(snap)

    # 4. Karar masasi ozeti (T+30 odakli, en cok kullanilacak vade)
    comparison: Dict = {}
    for s in snapshots:
        if s["label"] == "T+30":
            d = s["delta_vs_baseline"]
            comparison = {
                "net_worth_change_30d": d.get("net_deger", 0.0),
                "cash_change_30d": d.get("nakit_kasa", 0.0),
                "card_debt_change_30d": d.get("kart_borcu", 0.0),
                "loan_debt_change_30d": d.get("kredi_borcu", 0.0),
                "investment_change_30d": d.get("yatirim_deger", 0.0),
            }
            break

    return {
        "ok": True,
        "message": "Simulasyon tamamlandi.",
        "baseline": baseline_snap,
        "snapshots": snapshots,
        "event_log": world.event_log,
        "comparison": comparison,
    }