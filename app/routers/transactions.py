"""
Transaction CRUD + hizli giris (quick entry) + auto balance management.

NOTLAR:
- TransactionType bir str-enum ama Pydantic v2 + Literal kombinasyonu enum
  objesini stringe otomatik cevirmedigi icin response_model yerine manuel
  serialization yapiyoruz (dict doneriz). FastAPI bunu JSON yapar.
- BUG #009 cozumu: DELETE endpoint auto_revert_balance=True ile bakiyeyi
  geri cevirir.
"""

import logging
import math
import re
from datetime import date
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id, scope_filter, require_write  # M43 workspace scoping
from app.serializers import utc_isoformat  # BUG #092: datetime UTC suffix
# SEC-032: işlem tutarı SONLU olmalı (inf/NaN/taşma reddedilir); ≤0 kontrolü handler'daki
# manuel doğrulamada (dostça Türkçe mesaj + quick_text modu) kalır → FinansOptBakiye (sign-agnostik sonlu).
from app.schema_types import FinansOptBakiye
from app.money import D  # ADR-030: para Decimal coercion
from app.models import (
    User, Account, AccountType, Transaction, TransactionType,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transactions", tags=["transactions"], dependencies=[Depends(require_write())])


# ============================================================
# INLINE PYDANTIC SCHEMAS
# ============================================================

class TransactionCreate(BaseModel):
    """Quick-entry destekli olusturma."""
    account_id: Optional[int] = None
    transaction_type: Optional[Literal["income", "expense", "transfer"]] = None
    amount: FinansOptBakiye = None  # SEC-032: sonlu (≤0 kontrolü handler'da; quick_text'te None)
    # SEC-031: kullanıcı serbest-metin alanlarına CÖMERT üst sınır — DB bloat + prompt-injection
    # payload boyutu + koç context şişmesi koruması (meşru not/kategori çok altında kalır).
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    transaction_date: Optional[date] = None
    is_card_expense: Optional[bool] = None

    # Quick entry
    quick_text: Optional[str] = Field(None, max_length=200)
    auto_update_balance: Optional[bool] = True


class TransactionUpdate(BaseModel):
    """PUT icin partial guncelleme."""
    account_id: Optional[int] = None
    transaction_type: Optional[Literal["income", "expense", "transfer"]] = None
    amount: FinansOptBakiye = None  # SEC-032: sonlu (≤0 kontrolü handler'da; quick_text'te None)
    category: Optional[str] = Field(None, max_length=100)  # SEC-031
    description: Optional[str] = Field(None, max_length=1000)  # SEC-031
    transaction_date: Optional[date] = None
    is_card_expense: Optional[bool] = None
    auto_update_balance: Optional[bool] = True


# ============================================================
# YARDIMCI: Transaction -> dict (manuel serializer)
# ============================================================

def _txn_to_dict(txn: Transaction) -> dict:
    """Transaction modelini JSON-uyumlu dict'e cevir (enum'lari string yapar)."""
    ttype = txn.transaction_type
    if hasattr(ttype, "value"):
        ttype = ttype.value
    return {
        "id": txn.id,
        "user_id": txn.user_id,
        "account_id": txn.account_id,
        "transaction_type": ttype,
        "amount": txn.amount,
        "category": txn.category,
        "description": txn.description,
        "transaction_date": txn.transaction_date.isoformat() if txn.transaction_date else None,
        "is_card_expense": txn.is_card_expense,
        "created_at": utc_isoformat(txn.created_at),  # BUG #092: UTC suffix (yoksa JS -3h)
    }


# ============================================================
# YARDIMCI: Hesap bakiyesini transaction'a gore guncelle
# ============================================================

def _apply_to_balance(account: Account, txn_type, amount: float, reverse: bool = False) -> None:
    """
    Transaction tutarini hesabin bakiyesine uygular.

    reverse=False:
        cash + expense -> balance -= amount
        cash + income  -> balance += amount
        credit_card + expense -> balance += amount  (borc artar)
        credit_card + income  -> balance -= amount  (kart odendi, borc azalir)
        loan + expense (taksit) -> balance -= amount

    reverse=True: tersi (silme/update icin).
    """
    if account is None:
        return

    # M53: işaret konvansiyonu TEK KAYNAK (app/balance_rules.balance_delta). reverse = deltayı ters çevir.
    from app.balance_rules import balance_delta
    delta = balance_delta(account.account_type, txn_type, amount)
    account.balance += (-delta if reverse else delta)


# ============================================================
# YARDIMCI: Hizli giris parser
# ============================================================

QUICK_KEYWORDS = {
    "yemek":    {"category": "yemek",    "is_card": True},
    "kahve":    {"category": "yemek",    "is_card": True},
    "icecek":   {"category": "yemek",    "is_card": True},
    "kafe":     {"category": "yemek",    "is_card": True},
    "eglence":  {"category": "eglence",  "is_card": True},
    "sinema":   {"category": "eglence",  "is_card": True},
    "sigara":   {"category": "sigara",   "is_card": True},
    "ulasim":   {"category": "ulasim",   "is_card": False},
    "yakit":    {"category": "ulasim",   "is_card": False},
    "tasit":    {"category": "ulasim",   "is_card": False},
    "metro":    {"category": "ulasim",   "is_card": False},
    "otobus":   {"category": "ulasim",   "is_card": False},
    "taksi":    {"category": "ulasim",   "is_card": False},
    "fatura":   {"category": "fatura",   "is_card": False},
    "telefon":  {"category": "fatura",   "is_card": False},
    "internet": {"category": "fatura",   "is_card": False},
    "elektrik": {"category": "fatura",   "is_card": False},
    "saglik":   {"category": "saglik",   "is_card": False},
    "ilac":     {"category": "saglik",   "is_card": False},
    "doktor":   {"category": "saglik",   "is_card": False},
    "borc":     {"category": "borc_geri_odeme", "is_card": False},
    "alisveris":{"category": "alisveris", "is_card": True},
    "market":   {"category": "alisveris", "is_card": True},
    "diger":    {"category": "diger",    "is_card": False},
}


# FEAT-034: otomatik kategori önerisi. Yapılandırılmış girişte (UI formu) kullanıcı bir
# açıklama yazıp kategoriyi boş bıraktığında, açıklamadaki anahtar kelimeden kategori türetilir.
# Marka/işyeri adları da eşlenir (Migros → alisveris). quick-text zaten QUICK_KEYWORDS ile
# çıkarım yapıyor; bu, aynı kolaylığı normal forma taşır. Deterministik + test edilebilir;
# hiçbir zaman kullanıcının verdiği kategoriyi ezmez (yalnız boşsa doldurur).
MERCHANT_KEYWORDS = {
    # market / alışveriş
    "migros": "alisveris", "bim": "alisveris", "a101": "alisveris", "sok": "alisveris",
    "carrefour": "alisveris", "carrefoursa": "alisveris", "macrocenter": "alisveris",
    "getir": "alisveris", "trendyol": "alisveris", "hepsiburada": "alisveris",
    "amazon": "alisveris", "market": "alisveris",
    # yemek / kafe
    "yemeksepeti": "yemek", "starbucks": "yemek", "restoran": "yemek", "lokanta": "yemek",
    "burger": "yemek", "pizza": "yemek", "cafe": "yemek",
    # ulaşım / yakıt
    "opet": "ulasim", "shell": "ulasim", "bp": "ulasim", "petrol": "ulasim",
    "benzin": "ulasim", "uber": "ulasim", "bitaksi": "ulasim", "istanbulkart": "ulasim",
    # fatura / abonelik
    "netflix": "eglence", "spotify": "eglence", "youtube": "eglence", "exxen": "eglence",
    "turkcell": "fatura", "vodafone": "fatura", "turk telekom": "fatura", "superonline": "fatura",
    "elektrik": "fatura", "dogalgaz": "fatura", "igdas": "fatura", "iski": "fatura",
    # sağlık
    "eczane": "saglik", "hastane": "saglik", "medikal": "saglik",
}


def suggest_category(text: Optional[str]) -> Optional[str]:
    """
    Açıklama/işyeri metninden kategori türet (FEAT-034). Eşleşme yoksa None.
    Önce belirli marka adları (MERCHANT_KEYWORDS), sonra genel anahtar kelimeler
    (QUICK_KEYWORDS) kontrol edilir — böylece 'migros' → alisveris, 'taksi' → ulasim.

    KELİME SINIRI: tek kelimelik anahtarlar token kümesine göre eşlenir — düz substring
    DEĞİL. Aksi halde 'sok' → 'sokak', 'bim' → 'kimbilir' gibi yanlış pozitifler doğardı.
    Çok kelimeli anahtarlar ('turk telekom') boşlukla sarılı substring ile aranır.
    """
    if not text:
        return None
    low = text.strip().lower()
    tokens = set(re.findall(r"[a-zçğıöşü0-9]+", low))
    padded = " " + low + " "

    def _match(kw: str) -> bool:
        if " " in kw:  # çok kelimeli marka
            return f" {kw} " in padded
        return kw in tokens

    for kw, cat in MERCHANT_KEYWORDS.items():
        if _match(kw):
            return cat
    for kw, meta in QUICK_KEYWORDS.items():
        if _match(kw):
            return meta["category"]
    return None


def _parse_quick_text(text: str) -> dict:
    parts = text.strip().lower().split()
    if not parts:
        raise ValueError("Bos giris")

    try:
        amount = float(parts[0].replace(",", "."))
    except ValueError:
        raise ValueError(f"Gecerli tutar bulunamadi: '{parts[0]}'")
    # SEC-032: quick_text tutarı Pydantic şema doğrulamasını ATLAR (create'te amount None gelip
    # burada doldurulur) → sonlu/üst-sınır kontrolü BURADA yapılmalı; aksi halde "1e308 yemek"
    # veya "Infinity market" DB'ye sızıp rules_engine matematiğini bozar (nan `<=0`'ı da atlar).
    if not math.isfinite(amount):
        raise ValueError("Tutar sonlu bir sayı olmalı")
    if amount <= 0:
        raise ValueError("Tutar pozitif olmali")
    if amount > 1e12:  # schema_types._FIN_MAX ile aynı üst sınır (taşma/çöp değer)
        raise ValueError("Tutar makul üst sınırı (1e12) aşıyor")

    rest = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
    if not rest:
        return {"amount": amount, "category": "diger", "is_card_expense": False, "description": None}

    for keyword, meta in QUICK_KEYWORDS.items():
        if keyword in rest:
            return {
                "amount": amount,
                "category": meta["category"],
                "is_card_expense": meta["is_card"],
                "description": rest if rest != keyword else None,
            }

    return {
        "amount": amount,
        "category": rest.replace(" ", "_"),
        "is_card_expense": False,
        "description": None,
    }


# ============================================================
# ENDPOINTS — response_model yerine manual dict serialization
# ============================================================

@router.get("")
def list_transactions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=1000),  # BUG #154 (P2-5): ust sinir
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """Son N transaction (en yeni once)."""
    txns = (
        db.query(Transaction)
        .filter(scope_filter(Transaction, user.id, ws_id))  # M43 workspace scoping
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
    return [_txn_to_dict(t) for t in txns]


@router.post("", status_code=201)
def create_transaction(
    payload: TransactionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """
    Yeni islem ekle. Iki mod:
      A) Yapilandirilmis: transaction_type + amount + (opsiyonel digerleri)
      B) Hizli giris: quick_text='230 yemek'
    """
    data = payload.model_dump(exclude_none=True)

    # Hizli giris modu
    if data.get("quick_text"):
        try:
            parsed = _parse_quick_text(data["quick_text"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if not data.get("transaction_type"):
            data["transaction_type"] = "expense"
        data["amount"] = parsed["amount"]
        if not data.get("category"):
            data["category"] = parsed["category"]
        if "is_card_expense" not in data:
            data["is_card_expense"] = parsed["is_card_expense"]
        if not data.get("description"):
            data["description"] = parsed["description"] or data["quick_text"]

    # FEAT-034: kategori boşsa açıklamadan türet. Yalnız gider işlemlerinde ve kategori
    # verilmemişse — kullanıcının açık seçimini asla ezmez. Böylece UI formunda "Migros 240 TL"
    # yazıp kategoriyi boş bırakmak yeter; alisveris otomatik atanır.
    if not data.get("category") and data.get("transaction_type") == "expense":
        guess = suggest_category(data.get("description"))
        if guess:
            data["category"] = guess

    # Default hesap seçimi — DATA-018: yalnız quick-text için DEĞİL, HER create için (account_id
    # verilmemişse) varsayılan hesaba düş. Böylece hem UX korunur hem "yetim" işlem üretilmez.
    if not data.get("account_id"):
        if data.get("is_card_expense"):
            acc = (
                db.query(Account)
                .filter(scope_filter(Account, user.id, ws_id),  # M43
                        Account.account_type == AccountType.credit_card)
                .first()
            )
        else:
            acc = (
                db.query(Account)
                .filter(scope_filter(Account, user.id, ws_id),  # M43
                        Account.account_type == AccountType.cash)
                .first()
            )
        if acc:
            data["account_id"] = acc.id

    # Zorunlu alanlar
    if not data.get("transaction_type"):
        raise HTTPException(status_code=400, detail="transaction_type zorunlu")
    if not data.get("amount") or data["amount"] <= 0:
        raise HTTPException(status_code=400, detail="amount pozitif olmali")

    auto_update = data.pop("auto_update_balance", True)
    data.pop("quick_text", None)

    # Account bul — DATA-018: her işlem bir hesabı ETKİLEMELİ (bakiyesiz "yetim" işlem yok).
    # Varsayılan hesap seçimi (yukarıda) uygun hesap bulamadıysa account_id None kalır →
    # eskiden bakiyeye dokunmayan yanıltıcı bir işlem oluşuyordu. Artık reddedilir.
    if not data.get("account_id"):
        raise HTTPException(
            status_code=400,
            detail="Hesap belirtilmedi ve uygun varsayılan hesap yok. Önce bir nakit/kart hesabı ekle ya da account_id belirt.",
        )
    account = (
        db.query(Account)
        .filter(Account.id == data["account_id"], scope_filter(Account, user.id, ws_id))  # M43
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Hesap bulunamadi")

    # Transaction kaydi olustur — M43: aktif workspace'e bağla (yoksa None=legacy)
    txn = Transaction(user_id=user.id, workspace_id=ws_id, **data)
    db.add(txn)

    if auto_update and account:
        _apply_to_balance(account, txn.transaction_type, txn.amount, reverse=False)

    db.commit()
    db.refresh(txn)

    # BUG #141 fix (P1-8): GoalRule otomatik-tahsis motorunu TETİKLE. Eskiden
    # evaluate_rules_for_transaction TAM+TESTLİ ama hiçbir yerden çağrılmıyordu → kullanıcı
    # kural yaratsa da (POST /goals/rules) hiç allocation oluşmuyordu (yarım özellik). Kural
    # yoksa etki yok (opt-in). Hata transaction'ı bozmasın (post-commit, defensive).
    try:
        from app.goal_rules import evaluate_rules_for_transaction
        evaluate_rules_for_transaction(txn.id, db)
    except Exception as e:
        logger.warning(f"goal rule degerlendirme basarisiz (sessiz, txn zaten kayitli): {e}")

    return _txn_to_dict(txn)


@router.put("/{txn_id}")
def update_transaction(
    txn_id: int,
    payload: TransactionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """Transaction guncelle. Eski tutarın etkisini geri al, yeniyi uygula."""
    txn = (
        db.query(Transaction)
        .filter(Transaction.id == txn_id, scope_filter(Transaction, user.id, ws_id))  # M43
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Islem bulunamadi")

    update_data = payload.model_dump(exclude_unset=True)
    auto_update = update_data.pop("auto_update_balance", True)

    # BUG #087 fix: update yolu create ile aynı doğrulamayı yapmalı.
    # (a) amount <= 0 reddedilmeli — aksi halde negatif tutar _apply_to_balance'ta
    #     işareti ters çevirip bakiyeyi bozuyordu (gider güncellemesi bakiyeyi ARTIRIYORDU).
    if "amount" in update_data and (update_data["amount"] is None or update_data["amount"] <= 0):
        raise HTTPException(status_code=422, detail="Tutar pozitif olmalı (amount > 0).")
    # (b) account_id başka kullanıcının/var olmayan hesabına taşınamaz (create 404 veriyor;
    #     update sessizce kabul edip txn'i sahipsiz hesaba bağlıyordu).
    if "account_id" in update_data and update_data["account_id"] is not None:
        target = (
            db.query(Account)
            .filter(Account.id == update_data["account_id"], scope_filter(Account, user.id, ws_id))  # M43
            .first()
        )
        if not target:
            raise HTTPException(status_code=404, detail="Hedef hesap bulunamadi veya size ait degil.")

    # 1. Eski etki
    if auto_update and txn.account_id:
        old_account = (
            db.query(Account)
            .filter(Account.id == txn.account_id, scope_filter(Account, user.id, ws_id))  # M43
            .first()
        )
        if old_account:
            _apply_to_balance(old_account, txn.transaction_type, txn.amount, reverse=True)

    # 2. Alanlari guncelle
    for k, v in update_data.items():
        setattr(txn, k, v)

    # 3. Yeni etki
    if auto_update and txn.account_id:
        new_account = (
            db.query(Account)
            .filter(Account.id == txn.account_id, scope_filter(Account, user.id, ws_id))  # M43
            .first()
        )
        if new_account:
            _apply_to_balance(new_account, txn.transaction_type, txn.amount, reverse=False)

    db.commit()
    db.refresh(txn)
    return _txn_to_dict(txn)


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(
    txn_id: int,
    auto_revert_balance: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
):
    """
    Transaction sil. Default: silinen transaction'in bakiyeye olan etkisi
    geri alinir. False ise sadece kayit silinir.
    BUG #009 cozumu.
    """
    txn = (
        db.query(Transaction)
        .filter(Transaction.id == txn_id, scope_filter(Transaction, user.id, ws_id))  # M43
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Islem bulunamadi")

    # Bakiyeyi geri cevir
    if auto_revert_balance and txn.account_id:
        account = (
            db.query(Account)
            .filter(Account.id == txn.account_id, scope_filter(Account, user.id, ws_id))  # M43
            .first()
        )
        if account:
            _apply_to_balance(account, txn.transaction_type, txn.amount, reverse=True)

    db.delete(txn)
    db.commit()
    return None