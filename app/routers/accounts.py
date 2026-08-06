"""
Account endpoint'leri (5):
- GET    /api/accounts         - Tum hesaplari listele
- POST   /api/accounts         - Yeni hesap
- GET    /api/accounts/{id}    - Tek hesap
- PUT    /api/accounts/{id}    - Hesap guncelle (yatirim icin lot/fiyat -> balance otomatik)
- DELETE /api/accounts/{id}    - Hesap sil

Mukemmellestirici detay: Yatirim hesaplarinda lot_count veya current_price guncellenince
balance OTOMATIK = lot_count * current_price hesaplaniyor. Frontend tek alan
guncelliyor, bakiye kendiliginden doruluyor (Improvement Backlog'da konusulmustu).
"""

from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sqlalchemy.exc import IntegrityError

from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id, scope_filter, require_write  # M43 workspace scoping
from app.models import User, Account, AccountType, Transaction, RecurringExpense
from app.serializers import UtcDateTime  # BUG #092: datetime UTC suffix
# SEC-032: finansal float alanları sonlu olmalı (inf/NaN/taşma rules_engine'i çökertir).
# balance negatif olabilir (FinansBakiye); limit/faiz/lot/fiyat ≥0 (FinansOptOran).
from app.schema_types import FinansBakiye, FinansOptBakiye, FinansOptOran
from app.schemas import FiyatTazeligiMixin  # BUG #239 (D23): fiyat tazeliği tek kaynaktan

router = APIRouter(prefix="/api/accounts", tags=["accounts"], dependencies=[Depends(require_write())])


# ============================================================
# SCHEMAS
# ============================================================

class AccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    account_type: AccountType
    balance: FinansBakiye = 0.0  # SEC-032: sonlu (negatif olabilir)
    notes: Optional[str] = Field(None, max_length=2000)  # BUG #181
    # Kredi karti
    credit_limit: FinansOptOran = None  # SEC-032
    statement_day: Optional[int] = Field(None, ge=1, le=31)
    payment_day: Optional[int] = Field(None, ge=1, le=31)
    # Kredi
    interest_rate: FinansOptOran = None  # SEC-032
    monthly_payment: FinansOptOran = None  # SEC-032
    remaining_installments: Optional[int] = Field(None, ge=0)
    next_payment_date: Optional[date] = None
    # Yatirim
    fund_code: Optional[str] = Field(None, max_length=20)
    lot_count: FinansOptOran = None  # SEC-032
    cost_per_lot: FinansOptOran = None  # SEC-032
    current_price: FinansOptOran = None  # SEC-032
    is_emanet: bool = False


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    """Sadece gonderilen alanlar guncellenir. None'lar atlanir."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    balance: FinansOptBakiye = None  # SEC-032
    notes: Optional[str] = Field(None, max_length=2000)  # BUG #181
    credit_limit: FinansOptOran = None  # SEC-032
    statement_day: Optional[int] = Field(None, ge=1, le=31)
    payment_day: Optional[int] = Field(None, ge=1, le=31)
    interest_rate: FinansOptOran = None  # SEC-032
    monthly_payment: FinansOptOran = None  # SEC-032
    remaining_installments: Optional[int] = Field(None, ge=0)
    next_payment_date: Optional[date] = None
    fund_code: Optional[str] = Field(None, max_length=20)
    lot_count: FinansOptOran = None  # SEC-032
    cost_per_lot: FinansOptOran = None  # SEC-032
    current_price: FinansOptOran = None  # SEC-032
    is_emanet: Optional[bool] = None


class AccountOut(AccountBase, FiyatTazeligiMixin):
    """BUG #239 (D23): `fiyat_bayat`/`fiyat_yas` mixin'den türer — panel fiyatı "güncel"
    diye etiketlemeden önce yaşını bilir. Tazelik kuralı tek yerde (fund_tracker)."""
    id: int
    last_price_update: Optional[UtcDateTime] = None
    created_at: UtcDateTime
    updated_at: UtcDateTime

    model_config = {"from_attributes": True}  # BUG #118: Pydantic V2 (V1 class Config deprecated)


# ============================================================
# ENDPOINT'LER
# ============================================================

@router.get("", response_model=List[AccountOut])
def list_accounts(
    account_type: Optional[AccountType] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> List[AccountOut]:
    """
    Tum hesaplari listele. Opsiyonel filtre: ?account_type=cash|credit_card|loan|investment
    """
    q = db.query(Account).filter(scope_filter(Account, user.id, ws_id))  # M43 workspace scoping
    if account_type:
        q = q.filter(Account.account_type == account_type)
    return q.order_by(Account.account_type, Account.id).all()


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> AccountOut:
    """Yeni hesap olustur."""
    data = payload.model_dump()

    # Yatirim hesabinda lot ve fiyat varsa balance'i otomatik hesapla
    if (data.get("account_type") == AccountType.investment
            and data.get("lot_count") is not None
            and data.get("current_price") is not None):
        data["balance"] = float(data["lot_count"]) * float(data["current_price"])

    acc = Account(user_id=user.id, workspace_id=ws_id, **data)  # M43: aktif workspace'e bağla
    if data.get("current_price") is not None:
        acc.last_price_update = datetime.utcnow()

    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> AccountOut:
    """Tek hesap detayi."""
    acc = db.query(Account).filter(
        Account.id == account_id,
        scope_filter(Account, user.id, ws_id),  # M43 workspace scoping
    ).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Hesap bulunamadi (id={account_id})")
    return acc


@router.put("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int,
    payload: AccountUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> AccountOut:
    """
    Hesap guncelle. Sadece None olmayan alanlar yazilir.

    AKILLI BAKIYE GUNCELLEMESI:
    Eger hesap tipi 'investment' ise ve (lot_count veya current_price) degistirildiyse,
    balance otomatik = lot_count * current_price seklinde guncellenir.
    Boylece kullanici lot/fiyat girer, bakiyeyi ayrica girmesi gerekmez.

    Bu kullanicinin acikca 'balance' alanini gondermesi durumunda DEVRE DISI
    kalir (kullanicinin acik onceligi var).
    """
    acc = db.query(Account).filter(
        Account.id == account_id,
        scope_filter(Account, user.id, ws_id),  # M43 workspace scoping
    ).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Hesap bulunamadi (id={account_id})")

    update_data = payload.model_dump(exclude_unset=True)
    user_specified_balance = "balance" in update_data
    price_changed = "current_price" in update_data

    for k, v in update_data.items():
        setattr(acc, k, v)

    # Akilli bakiye: yatirim + lot/fiyat degisti + kullanici balance acikca vermedi
    if (acc.account_type == AccountType.investment
            and not user_specified_balance
            and acc.lot_count is not None
            and acc.current_price is not None
            and ("lot_count" in update_data or "current_price" in update_data)):
        acc.balance = float(acc.lot_count) * float(acc.current_price)

    # Fiyat degistiyse zaman damgasini guncelle
    if price_changed:
        acc.last_price_update = datetime.utcnow()

    db.commit()
    db.refresh(acc)
    return acc


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> None:
    """
    Hesabi sil. EMANET hesaplari korumaliyiz - silmesini engelliyoruz.

    Mukemmellestirici: Bu hesaba bagli transaction varsa kullanici uyarilmali.
    Su an cascade=None oldugundan transaction varken silmeye calisirsa SQL hatasi
    doner. Bu davranisi sonra duzenli hata mesajina cevirebiliriz.
    """
    acc = db.query(Account).filter(
        Account.id == account_id,
        scope_filter(Account, user.id, ws_id),  # M43 workspace scoping
    ).first()
    if not acc:
        raise HTTPException(status_code=404, detail=f"Hesap bulunamadi (id={account_id})")

    if acc.is_emanet:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Emanet hesabi silinemez (MC1 koruma).",
        )

    # BUG #091 fix: FK artık ENFORCE ediliyor (PRAGMA foreign_keys=ON, BUG #060). Bağlı
    # transaction/recurring expense varken silmek IntegrityError → HTTP 500 veriyordu.
    # Önce bağımlı kayıtları say, kullanıcıya düzgün 409 döndür (veri kaybı yok).
    txn_count = db.query(Transaction).filter(Transaction.account_id == account_id).count()  # scope-exempt: sahipliği yukarıda doğrulanmış hesabın çocuk sayımı
    exp_count = db.query(RecurringExpense).filter(RecurringExpense.account_id == account_id).count()  # scope-exempt: aynı hesabın çocuk sayımı
    if txn_count or exp_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Hesap silinemez: {txn_count} işlem ve {exp_count} düzenli gider bağlı. "
                f"Önce bunları silin veya başka hesaba taşıyın."
            ),
        )

    try:
        db.delete(acc)
        db.commit()
    except IntegrityError:
        db.rollback()  # başka bir FK bağımlılığı (ör. goal allocation) — session'ı temizle
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hesap başka kayıtlara bağlı olduğu için silinemedi.",
        )
    return None