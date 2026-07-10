"""
H2G5 Goal Rules — Otomatik Allocation Kural Motoru (ADR-024)

Yeni bir Transaction kaydedildiğinde evaluate_rules_for_transaction çağrılır.
Tüm aktif GoalRule'lar sırayla değerlendirilir; eşleşenler için GoalAllocation
yaratılır. Birden fazla kural aynı transaction'a eşleşebilir (stack yaklaşımı —
Monarch Money Goal 3.0 ile aynı felsefe).

Tasarım:
  - ADR-001: tamamen deterministik Python, LLM yok
  - db.flush() kullanır, db.commit() kullanmaz
  - Duplicate (goal_id, transaction_id): IntegrityError sessizce skip edilir
  - Paused/achieved/abandoned goal'lar atlanır

Desteklenen criteria anahtarları:
  tx_type               : "income" | "expense" | "transfer"
  amount_min            : Decimal — min abs(amount)
  amount_max            : Decimal — max abs(amount)
  account_id            : int — kaynak hesap ID'si (Transaction.account_id)
  account_type          : str | list[str] — kaynak hesap tipi
                          ("cash", "credit_card", "loan", "investment")
  description_contains  : str — açıklamada geçen anahtar kelime (case-insensitive)

GUNCELLEMELER:
  BUG #059 fix: account_type criteria eşleşmesinde str(acc.account_type)
    ("AccountType.cash") yerine acc.account_type.value ("cash") kullanılır.
    Önceki kod account_type kriterli HER GoalRule'u sessizce ölü bırakıyordu
    (tx_type dalı ~satır 102'de zaten .value kullanıyordu). Kalite serüveni RULE-001.
"""
from __future__ import annotations

from decimal import Decimal
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.goal_engine import refresh_goal


def evaluate_rules_for_transaction(
    transaction_id: int, db: Session
) -> List[models.GoalAllocation]:
    """Tek transaction için tüm aktif kuralları değerlendir.

    Eşleşen her kural için GoalAllocation yarat.
    Etkilenen goal'lerin cache'ini toplu olarak tazele.
    Döndürülen liste: yaratılan GoalAllocation nesneleri.
    """
    tx = db.query(models.Transaction) \
           .filter(models.Transaction.id == transaction_id).first()
    if not tx:
        return []

    rules = (
        db.query(models.GoalRule)
        .filter(models.GoalRule.is_active.is_(True))
        .order_by(models.GoalRule.priority.asc(), models.GoalRule.id.asc())
        .all()
    )

    created: List[models.GoalAllocation] = []
    affected_goals: set = set()

    for rule in rules:
        # Pasif/tamamlanmış goal'leri atla (lazy load — goal relationship var)
        if rule.goal.status != "active":
            continue

        if not _matches(tx, rule.criteria, db):
            continue

        alloc_amount = _compute_allocation_amount(tx, rule)
        if alloc_amount == 0:
            continue

        try:
            nested = db.begin_nested()  # SAVEPOINT — sadece bu allocation atomik
            alloc = models.GoalAllocation(
                goal_id=rule.goal_id,
                transaction_id=tx.id,
                amount=alloc_amount,
                source="rule",
                rule_id=rule.id,
            )
            db.add(alloc)
            db.flush()
            nested.commit()
            db.refresh(alloc)
            created.append(alloc)
            affected_goals.add(rule.goal_id)
        except IntegrityError:
            nested.rollback()  # Sadece bu savepoint geri alınır, session sağlam kalır
            # Aynı (goal, tx) zaten mevcut — sessizce geç

    for gid in affected_goals:
        refresh_goal(gid, db)

    return created


def _matches(tx: models.Transaction, criteria: dict, db: Session) -> bool:
    """Tek kural criteria'sını bir transaction'a uygula. True = eşleşti."""

    # tx_type — .value kullan: str(enum) "ClassName.value" döndürür
    if "tx_type" in criteria:
        if tx.transaction_type.value != criteria["tx_type"]:
            return False

    # amount_min / amount_max — abs değer üzerinden
    tx_abs = abs(Decimal(str(tx.amount)))
    if "amount_min" in criteria:
        if tx_abs < Decimal(str(criteria["amount_min"])):
            return False
    if "amount_max" in criteria:
        if tx_abs > Decimal(str(criteria["amount_max"])):
            return False

    # account_id — kaynak hesap ID eşleşmesi
    if "account_id" in criteria:
        if tx.account_id != criteria["account_id"]:
            return False

    # account_type — kaynak hesabın tipi (string veya liste)
    if "account_type" in criteria:
        if not tx.account_id:
            return False
        acc = db.query(models.Account) \
                .filter(models.Account.id == tx.account_id).first()
        if not acc:
            return False
        allowed = criteria["account_type"]
        if isinstance(allowed, str):
            allowed = [allowed]
        # BUG #059 fix: str(enum) "AccountType.cash" döndürür, criteria "cash" bekler.
        # tx_type dalı (satır ~102) zaten .value kullanıyor; buraya da uygulandı.
        if acc.account_type.value not in allowed:
            return False

    # description_contains — case-insensitive substring
    if "description_contains" in criteria:
        needle = criteria["description_contains"].lower()
        hay = (tx.description or "").lower()
        if needle not in hay:
            return False

    return True


def _compute_allocation_amount(
    tx: models.Transaction, rule: models.GoalRule
) -> Decimal:
    """Kural allocation_type'ına göre TL miktarı hesapla."""
    tx_amount = Decimal(str(tx.amount))
    # BUG #090 fix: full/percent dalları da işaret-farkındalığını uygulamalı (fixed dalı
    # #064'te düzeltilmişti, bunlar unutulmuş → gidere eşleşen full/percent kural progress'i
    # şişiriyordu). tx.amount DB'de HER ZAMAN pozitif; yön transaction_type'ta.
    # İŞARET KURALI: yalnız GİDER withdrawal (−); gelir VE transfer contribution (+).
    # (Transfer bir hesaba akış olarak goal'a pozitif katkı sayılır — bkz. test_09.)
    sign = Decimal("-1") if tx.transaction_type.value == "expense" else Decimal("1")

    if rule.allocation_type == "full":
        return sign * tx_amount

    elif rule.allocation_type == "percent":
        if rule.allocation_value is None:
            return Decimal("0")
        pct = Decimal(str(rule.allocation_value)) / Decimal("100")
        return sign * (tx_amount * pct).quantize(Decimal("0.01"))

    elif rule.allocation_type == "fixed":
        if rule.allocation_value is None:
            return Decimal("0")
        fixed = Decimal(str(rule.allocation_value))
        # BUG #064 fix (GR-001) + #090: işaret tx_amount'tan gelmez (hep pozitif). Gidere
        # eşleşen "fixed" kural withdrawal (−) olmalı; gelir/transfer (+). full/percent ile hizalı.
        return sign * fixed

    return Decimal("0")
