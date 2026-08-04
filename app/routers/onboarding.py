"""
Onboarding — isteğe bağlı DEMO VERİ (P3.5 / H5, BUG #194).

Sorun: yeni kullanıcı bomboş bir ekranla karşılaşıyor. "Örnek veri" ihtiyacı vardı ama
tek çözüm `scripts/setup_data.py`'ydi — o da **başkasının (kullanıcının) kanonik verisini**
yükler ve `drop_all` yapar; bir beta kullanıcısına asla bulaşmamalı.

Karar:
  - Demo veri **isteğe bağlıdır** (kullanıcı ister), kayıtta otomatik yüklenmez.
  - **Tek tuşla, TAM olarak silinebilir** — bunun için yaratılan her satırın kimliği
    `demo_data_markers` tablosunda tutulur. Silme, yalnız o satırları siler; kullanıcının
    kendi girdiği verilere ASLA dokunmaz (işaretsiz satır silinmez).
  - Veriler jeneriktir (kişi adı/banka markası yok — BUG #166/#168 ailesi).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id, scope_filter, require_write
from app.models import (
    User, Account, AccountType, Transaction, TransactionType, RecurringIncome,
    MasterCheckpoint, CheckpointType, Goal, DemoDataMarker,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"],
                   dependencies=[Depends(require_write())])

# Silme sırası: çocuk → ebeveyn (FK ihlali olmasın)
_SILME_SIRASI = ("transactions", "recurring_incomes", "goals", "master_checkpoints", "accounts")
_MODEL_HARITASI = {
    "accounts": Account,
    "transactions": Transaction,
    "recurring_incomes": RecurringIncome,
    "master_checkpoints": MasterCheckpoint,
    "goals": Goal,
}


class DemoDurumu(BaseModel):
    yuklu: bool
    satir_sayisi: int


def _isaretle(db: Session, user_id: int, tablo: str, satir_id: int) -> None:
    db.add(DemoDataMarker(user_id=user_id, table_name=tablo, row_id=satir_id))


@router.get("/demo", response_model=DemoDurumu)
def demo_durumu(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.query(DemoDataMarker).filter(DemoDataMarker.user_id == user.id).count()
    return DemoDurumu(yuklu=n > 0, satir_sayisi=n)


@router.post("/demo", response_model=DemoDurumu, status_code=status.HTTP_201_CREATED)
def demo_yukle(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
):
    """Jenerik örnek veri yükler (kullanıcının kendi verisine dokunmaz, izlenebilir)."""
    if db.query(DemoDataMarker).filter(DemoDataMarker.user_id == user.id).count() > 0:
        raise HTTPException(409, "Demo veri zaten yüklü. Önce kaldırabilirsin.")

    bugun = date.today()

    kasa = Account(user_id=user.id, workspace_id=ws_id, name="Örnek Vadesiz Hesap",
                   account_type=AccountType.cash, balance=15000.0,
                   notes="Demo veri — istediğin an kaldırabilirsin.")
    kart = Account(user_id=user.id, workspace_id=ws_id, name="Örnek Kredi Kartı",
                   account_type=AccountType.credit_card, balance=-3200.0,
                   credit_limit=20000.0, statement_day=5, payment_day=20,
                   notes="Demo veri")
    db.add_all([kasa, kart])
    db.flush()
    _isaretle(db, user.id, "accounts", kasa.id)
    _isaretle(db, user.id, "accounts", kart.id)

    maas = RecurringIncome(user_id=user.id, workspace_id=ws_id, name="Örnek Maaş",
                           amount=42000.0, day_of_month=15, is_active=True,
                           notes="Demo veri")
    db.add(maas)
    db.flush()
    _isaretle(db, user.id, "recurring_incomes", maas.id)

    for gun_once, tutar, kategori, aciklama in (
        (2, 480.0, "market", "Örnek market alışverişi"),
        (5, 1250.0, "fatura", "Örnek elektrik/su faturası"),
        (9, 300.0, "ulasim", "Örnek ulaşım harcaması"),
    ):
        tx = Transaction(user_id=user.id, workspace_id=ws_id, account_id=kasa.id,
                         transaction_type=TransactionType.expense, amount=tutar,
                         category=kategori, description=aciklama,
                         transaction_date=bugun - timedelta(days=gun_once))
        db.add(tx)
        db.flush()
        _isaretle(db, user.id, "transactions", tx.id)

    hedef = Goal(user_id=user.id, workspace_id=ws_id, goal_type="cash_target",
                 title="Örnek Hedef: 3 aylık acil fon", target_amount=Decimal("50000"),
                 status="active")
    db.add(hedef)
    db.flush()
    _isaretle(db, user.id, "goals", hedef.id)

    kural = MasterCheckpoint(
        user_id=user.id, workspace_id=ws_id, title="Örnek kural: nakit tabanı",
        description="Nakdim 5.000 TL'nin altına inmesin (bu bir demo kuralıdır — "
                    "kendi kuralını yazınca bunu silebilirsin).",
        checkpoint_type=CheckpointType.red_line, priority=2, is_active=True,
        rule_type="min_cash_floor", rule_params='{"amount": 5000}')
    db.add(kural)
    db.flush()
    _isaretle(db, user.id, "master_checkpoints", kural.id)

    db.commit()
    n = db.query(DemoDataMarker).filter(DemoDataMarker.user_id == user.id).count()
    logger.info("[onboarding] demo veri yuklendi user_id=%s satir=%s", user.id, n)
    return DemoDurumu(yuklu=True, satir_sayisi=n)


@router.delete("/demo", response_model=DemoDurumu)
def demo_kaldir(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
):
    """YALNIZ demo olarak işaretlenmiş satırları siler — kullanıcının verisi korunur."""
    isaretler = (db.query(DemoDataMarker)
                 .filter(DemoDataMarker.user_id == user.id).all())
    if not isaretler:
        return DemoDurumu(yuklu=False, satir_sayisi=0)

    by_table: dict[str, list[int]] = {}
    for m in isaretler:
        by_table.setdefault(m.table_name, []).append(m.row_id)

    for tablo in _SILME_SIRASI:
        idler = by_table.get(tablo)
        if not idler:
            continue
        model = _MODEL_HARITASI[tablo]
        (db.query(model)
           .filter(model.id.in_(idler), scope_filter(model, user.id, ws_id))
           .delete(synchronize_session=False))

    (db.query(DemoDataMarker)
       .filter(DemoDataMarker.user_id == user.id)
       .delete(synchronize_session=False))
    db.commit()
    logger.info("[onboarding] demo veri kaldirildi user_id=%s", user.id)
    return DemoDurumu(yuklu=False, satir_sayisi=0)
