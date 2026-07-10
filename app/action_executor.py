"""
Action Executor — Propose Action Onay-Uygulama Akışı

Akış:
1. Koç propose_action çağırır → PendingAction (status=pending)
2. Kullanıcı 'Onayla' der → execute_pending_action(action_id, db) çalışır
3. Bu modül payload'ı parse eder, DB'yi günceller, status='executed' yapar
4. Hata olursa status='failed' + error_message

Aksiyon türleri:
- update_account_balance     — hesap bakiyesi değişimi
- add_transaction            — gelir/gider kaydı
- mark_debt_paid             — kişisel borç ödendi
- sell_investment            — yatırım satışı (lot azalır + nakit artar)
- update_fund_price          — manuel fiyat güncelleme
- add_master_checkpoint      — yeni kırmızı çizgi ekle

KRITIK: MC1 (Emanet) gibi kuralları bu modül ENFORCE eder.
Emanet hesabı satma aksiyonu DB'ye yazılmaz, hata döner.

GÜNCELLEMELER:
- 4 May 2026 BUG #031 fix: execute_pending_action response'una Türkçe 'message' field eklendi.
  _fmt() Türkçe sayı formatı yardımcısı + _build_action_message() helper eklendi.
  _execute_add_transaction return'üne 'account_name' eklendi.
- 4 May 2026 BUG #032 fix: _fmt_lot() eklendi — lot değerleri tam sayıysa int gösterilir (4.0→4).
- 4 May 2026 BUG #039 fix: _normalize_transaction_payload() LLM açıkça nakit/banka hesabı
  seçtiyse kart varsayılanına yönlendirmez; account_id varsa ve kredi kartı değilse payload'a dokunulmaz.
- 6 Tem 2026 BUG #068 fix (AE-002/P0-2): _execute_sell_investment satış gelirinin gideceği
  hesabı MUTASYONDAN ÖNCE doğrular; geçersiz/emanet/eksik hesapta lot düşürmeden başarısız döner
  (eskiden net_eline_gecen hiçbir hesaba yatmadan lot düşüp success dönüyordu → para kaybı).
- 6 Tem 2026 BUG #069 fix (AE-001/P0-1): execute_pending_action post-commit trigger'ı ayrı try'a
  alındı — trigger hatası zaten 'executed' aksiyonu 'failed' işaretleyip çift-sayıma yol açmasın.
"""

import json
import logging
from datetime import datetime, date
from typing import Dict, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import (
    Account, AccountType, Transaction, TransactionType,
    PersonalDebt, DebtDirection, MasterCheckpoint, CheckpointType,
    PendingAction, ActionStatus,
)
from app.rules_engine import simulate_partial_sale


# BUG #025/#026 fix: Kart kategorileri (QUICK_KEYWORDS'deki is_card=True olanlar)
_CARD_CATEGORIES = {"yemek", "eglence", "sigara", "alisveris", "market"}
_TR_NORM = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiоsuCGIOSU")  # BUG #026: Türkçe karakter normalize

# BUG #042 fix: Hesap anahtar kelimesi — word boundary + çekim eki, false-positive'siz
import re as _re
_ACCOUNT_KEYWORD_RE = _re.compile(
    r'\b(kart(?!on\b)\w*|hesap\w*|hesab\w*|nakit\w*|enpara\w*|ziraat\w*|banka\w*)\b',
    _re.IGNORECASE,
)
# BUG #044 fix: Summary'de tarih ifadesi var ama payload'da transaction_date yok → tutarsızlık
_DATE_KEYWORD_RE = _re.compile(
    r'\b('
    r'ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık'
    r'|ocakta|şubatta|martta|nisanda|mayısta|haziranda|temmuzda|ağustosta|eylülde|ekimde|kasımda|aralıkta'
    r'|d[uü]n|bugün|bugun|geçen\s+hafta|gecen\s+hafta|geçen\s+ay|gecen\s+ay'
    r'|\d+\s+g[uü]n\s+[oö]nce'
    r'|\d{1,2}[./]\d{1,2}[./]\d{2,4}'
    r'|\d{4}-\d{2}-\d{2}'
    # BUG #114 fix: eskiden ['']  içindeki DÜZ apostrof (U+0027) r'...' raw string'i erken
    # kapatıyordu → karakter sınıfı boş [] oluyor, "3'ünde/5'inde" gibi Türkçe sıralı tarihler
    # YAKALANMIYOR + \w kaçış-uyarısı. Çift-tırnak raw + hem düz (') hem kıvrık (’) apostrof:
    r"|tarihinde|tarihli|\d{1,2}['’]\w+nde|\d{1,2}['’]\w+da"
    r')\b',
    _re.IGNORECASE,
)


def _cat_normalize(cat: str) -> str:
    """BUG #026: 'Eğlence' → 'eglence' — büyük harf + Türkçe aksan normalize."""
    return cat.lower().translate(_TR_NORM)


def _fmt(x: float) -> str:
    """BUG #031 fix: Sayıyı Türkçe format ile döner: 1234.56 → '1.234,56'"""
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_lot(x) -> str:
    """BUG #032 fix: Tam sayıysa int göster (4.0 → 4), kesirliyse virgüllü (2.5 → 2,5)"""
    try:
        f = float(x)
        if f == int(f):
            return str(int(f))
        return f"{f:.2f}".replace(".", ",").rstrip("0").rstrip(",")
    except (ValueError, TypeError):
        return str(x)


def _normalize_transaction_payload(payload: Dict, user_id: int, db: Session) -> Dict:
    """BUG #025/#026: Kategori normalize et, kart listesindeyse account_id ve is_card_expense zorla."""
    raw_category = payload.get("category", "")
    category = _cat_normalize(raw_category)

    if category not in _CARD_CATEGORIES:
        return payload

    # BUG #039: LLM açıkça nakit/banka hesabı seçtiyse override etme.
    # Sadece account_id yoksa veya zaten kredi kartıysa kart varsayılanına yönlendir.
    explicit_account_id = payload.get("account_id")
    if explicit_account_id is not None:
        explicit_account = db.query(Account).filter(
            Account.id == explicit_account_id,
            Account.user_id == user_id,
        ).first()
        if explicit_account and explicit_account.account_type != AccountType.credit_card:
            logger.info(
                f"BUG #039: kategori='{category}' kart listesinde ama "
                f"kullanici acikca '{explicit_account.name}' (id={explicit_account_id}) sectisi - dokunulmadi"
            )
            return payload

    card = db.query(Account).filter(
        Account.user_id == user_id,
        Account.account_type == AccountType.credit_card,
    ).first()
    if not card:
        return payload

    original_account = payload.get("account_id")
    logger.info(
        f"BUG #025/#026: kategori='{raw_category}'->'{category}' kart varsayilanina yonlendirildi "
        f"(account_id {original_account} -> {card.id}, is_card_expense=True)"
    )
    # BUG #026: normalize edilmiş category DB'ye yazılır (tutarlılık)
    return {**payload, "category": category, "account_id": card.id, "is_card_expense": True}


# ============================================================
# 1. PROPOSE — Koç bir aksiyon önerir, DB'ye 'pending' yazılır
# ============================================================

def propose_action(
    db: Session,
    user_id: int,
    action_type: str,
    payload: Dict,
    summary: str,
    user_message: str = "",
) -> PendingAction:
    """
    Koçun önerdiği aksiyonu PendingAction tablosuna kaydeder.

    Args:
        db: SQLAlchemy session
        user_id: Hangi kullanıcı için
        action_type: Aksiyon türü (yukarıdaki listeden biri)
        payload: Aksiyon verisi (dict, JSON serialize edilebilir olmalı)
        summary: Kullanıcıya gösterilecek tek cümle özet

    Returns:
        Yeni oluşturulan PendingAction kaydı (status=pending)
    """
    valid_types = {
        "update_account_balance",
        "add_transaction",
        "mark_debt_paid",
        "sell_investment",
        "update_fund_price",
        "add_master_checkpoint",
    }
    if action_type not in valid_types:
        raise ValueError(f"Bilinmeyen aksiyon türü: {action_type}")

    warning = None
    if action_type == "add_transaction":
        # BUG #042 fix: Gider işlemlerinde hesap anahtar kelimesi zorunlu
        if (payload.get("transaction_type") == "expense"
                and user_message
                and not _ACCOUNT_KEYWORD_RE.search(user_message)):
            raise ValueError("HESAP_BELIRSIZ")
        # BUG #044 fix: Summary'de tarih var ama payload'da yok → tutarsızlık
        if (summary
                and _DATE_KEYWORD_RE.search(summary)
                and not payload.get("transaction_date")):
            raise ValueError("TARIH_BELIRSIZ")
        payload = _normalize_transaction_payload(payload, user_id, db)
        # BUG #027: Kart limit aşımı uyarısı — DB rejection yok, kullanıcı karar verir
        if payload.get("is_card_expense") and payload.get("account_id"):
            card = db.query(Account).filter(
                Account.id == payload["account_id"],
                Account.user_id == user_id,
            ).first()
            if card and card.credit_limit:
                amount = float(payload.get("amount", 0))
                projected = card.balance + amount
                if projected > card.credit_limit:
                    overage = round(projected - card.credit_limit, 2)
                    warning = (
                        f"⚠️ Bu işlem kart limitini {overage:,.2f} TL aşacak "
                        f"(mevcut borç: {card.balance:,.2f} TL, limit: {card.credit_limit:,.2f} TL)"
                    )
                    logger.warning(f"BUG #027: {warning}")

    pending = PendingAction(
        user_id=user_id,
        action_type=action_type,
        payload=json.dumps(payload, ensure_ascii=False, default=str),
        summary=summary,
        status=ActionStatus.pending,
        warning=warning,
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)
    # SQLAlchemy expire workaround: instance attribute olarak da sakla
    pending._warning_text = warning
    return pending


def _build_action_message(action_type: str, result: Dict) -> str:
    """BUG #031 fix: Aksiyon sonucunu Türkçe özet mesaja çevirir (Toast için)."""
    try:
        if action_type == "sell_investment":
            sim = result.get("satis_simulasyonu", {})
            return (
                f"{_fmt_lot(sim.get('satilan_lot', '?'))} lot {result.get('investment_name', '?')} satıldı. "  # BUG #032 fix
                f"Elde edilen: {_fmt(sim.get('net_eline_gecen', 0))} TL "
                f"(stopaj: {_fmt(sim.get('stopaj', 0))} TL). "
                f"Kalan: {_fmt_lot(result.get('kalan_lot', 0))} lot."  # BUG #032 fix
            )
        if action_type == "add_transaction":
            account_name = result.get("account_name") or ""
            account_part = f" {account_name} hesabına" if account_name else ""
            return (
                f"{_fmt(result.get('amount', 0))} TL {result.get('category', '?')} işlemi"
                f"{account_part} kaydedildi."
            )
        if action_type == "mark_debt_paid":
            counterparty = result.get("counterparty", "?")
            amount = result.get("amount", 0)
            if result.get("direction") == "receivable":
                return f"{counterparty} alacağı tahsil edildi: {_fmt(amount)} TL."
            return f"{counterparty}'a borç ödendi: {_fmt(amount)} TL."
        if action_type == "update_account_balance":
            return (
                f"{result.get('account_name', '?')} bakiyesi güncellendi: "
                f"{_fmt(result.get('old_balance', 0))} → {_fmt(result.get('new_balance', 0))} TL."
            )
        if action_type == "update_fund_price":
            return result.get("message", "Fon fiyatı güncellendi.")
        if action_type == "add_master_checkpoint":
            return f"Yeni kural eklendi: '{result.get('title', '?')}'."
    except Exception:
        pass
    return "Aksiyon uygulandı."


# ============================================================
# 2. EXECUTE — Onaylanmış aksiyonu DB'ye uygula
# ============================================================

def _mark_recurring_triggered(db: Session, pending: PendingAction, payload: Dict) -> None:
    """
    BUG #070 (P0-15): recurring kaynaklı aksiyon GERÇEKTEN executed olunca kaynak
    RecurringIncome/Expense'in last_triggered_year_month'unu işaretler. Bu iş eskiden
    trigger anında (propose sırasında) yapılıyordu; reddedilen/başarısız gider "bu ay
    halledildi" sayılıp bir daha tetiklenmiyordu (sessiz veri kaybı). Commit YAPMAZ —
    çağıran execute_pending_action status='executed' ile aynı commit'te yazar.
    """
    if not getattr(pending, "source_recurring_id", None):
        return
    from app.models import RecurringIncome, RecurringExpense
    td = payload.get("transaction_date")
    ym = td[:7] if isinstance(td, str) and len(td) >= 7 else \
        f"{datetime.utcnow().year}-{datetime.utcnow().month:02d}"
    if pending.source_recurring_type == "income":
        rec = db.query(RecurringIncome).filter(RecurringIncome.id == pending.source_recurring_id).first()
    elif pending.source_recurring_type == "expense":
        rec = db.query(RecurringExpense).filter(RecurringExpense.id == pending.source_recurring_id).first()
    else:
        rec = None
    if rec is not None:
        rec.last_triggered_year_month = ym


def execute_pending_action(db: Session, action_id: int, user_id: int) -> Dict:
    """
    PendingAction'ı uygular. Onay sonrası çağrılır.

    Returns:
        {
            "success": bool,
            "action_type": str,
            "result": dict | None,    # her aksiyon kendi sonucunu döner
            "error": str | None,
        }
    """
    pending = (
        db.query(PendingAction)
        .filter(
            PendingAction.id == action_id,
            PendingAction.user_id == user_id,
        )
        .first()
    )

    if not pending:
        return {"success": False, "error": f"Aksiyon bulunamadi: id={action_id}"}

    if pending.status != ActionStatus.pending:
        return {
            "success": False,
            "error": f"Aksiyon zaten '{pending.status.value}' durumunda — tekrar uygulanamaz."
        }

    try:
        payload = json.loads(pending.payload)
    except json.JSONDecodeError as e:
        _mark_failed(db, pending, f"Payload parse hatasi: {e}")
        return {"success": False, "error": str(e)}

    # Dispatcher
    handlers = {
        "update_account_balance": _execute_update_account_balance,
        "add_transaction": _execute_add_transaction,
        "mark_debt_paid": _execute_mark_debt_paid,
        "sell_investment": _execute_sell_investment,
        "update_fund_price": _execute_update_fund_price,
        "add_master_checkpoint": _execute_add_master_checkpoint,
    }
    handler = handlers.get(pending.action_type)
    if not handler:
        _mark_failed(db, pending, f"Bilinmeyen aksiyon: {pending.action_type}")
        return {"success": False, "error": f"Handler yok: {pending.action_type}"}

    try:
        result = handler(db, user_id, payload)

        # Başarısız iş mantığı (örn. emanet ihlali)
        if not result.get("success", False):
            _mark_failed(db, pending, result.get("message", "Uygulama basarisiz."))
            return {
                "success": False,
                "action_type": pending.action_type,
                "error": result.get("message"),
            }

        # Başarılı — kaydı 'executed' işaretle
        pending.status = ActionStatus.executed
        pending.resolved_at = datetime.utcnow()
        # BUG #070 fix (P0-15): recurring last_triggered'i SADECE gerçekten executed olunca
        # işaretle (status ile aynı commit'te). Reddedilen/başarısız kayıt re-triggerable kalır.
        _mark_recurring_triggered(db, pending, payload)
        db.commit()
        # BUG #069 fix (P0-1): post-commit tetikleyici AYRI try. Aksiyon zaten 'executed'
        # (para/mutasyon kalıcı); trigger patlarsa asla 'failed' işaretleme — aksi halde
        # kullanıcı "başarısız" görüp tekrar tetikler, mutasyon çift uygulanır (çift-sayım).
        try:
            from app.scheduler import trigger_after_action_resolution
            trigger_after_action_resolution(db, user_id)
        except Exception as te:
            logger.warning("trigger_after_action_resolution basarisiz (aksiyon zaten executed): %s", te)

        return {
            "success": True,
            "action_type": pending.action_type,
            "result": result,
            "message": _build_action_message(pending.action_type, result),  # BUG #031 fix
        }

    except Exception as e:
        db.rollback()
        _mark_failed(db, pending, f"Beklenmeyen hata: {e}")
        return {"success": False, "error": str(e)}


def reject_pending_action(db: Session, action_id: int, user_id: int, reason: Optional[str] = None) -> Dict:
    """Kullanıcı 'Reddet' dediğinde aksiyon iptal edilir, DB'ye dokunulmaz."""
    pending = (
        db.query(PendingAction)
        .filter(
            PendingAction.id == action_id,
            PendingAction.user_id == user_id,
        )
        .first()
    )
    if not pending:
        return {"success": False, "error": "Aksiyon bulunamadi."}
    if pending.status != ActionStatus.pending:
        return {"success": False, "error": f"Aksiyon zaten '{pending.status.value}'."}

    pending.status = ActionStatus.rejected
    pending.resolved_at = datetime.utcnow()
    if reason:
        pending.error_message = reason
    db.commit()
    # Wave-2 H1G2: olay-tetikli action_rejection_pattern
    from app.scheduler import trigger_after_action_resolution
    trigger_after_action_resolution(db, user_id)
    return {"success": True, "action_id": action_id, "status": "rejected"}


def _mark_failed(db: Session, pending: PendingAction, error_message: str) -> None:
    """Aksiyonu 'failed' olarak işaretle."""
    pending.status = ActionStatus.failed
    pending.error_message = error_message
    pending.resolved_at = datetime.utcnow()
    db.commit()


# ============================================================
# 3. HANDLER'LAR — Her aksiyon türü için uygulama mantığı
# ============================================================

def _execute_update_account_balance(db: Session, user_id: int, payload: Dict) -> Dict:
    """
    Hesap bakiyesi güncelle.
    Payload: {"account_id": int, "new_balance": float, "reason": str?}
    """
    account_id = payload.get("account_id")
    new_balance = payload.get("new_balance")
    if account_id is None or new_balance is None:
        return {"success": False, "message": "account_id ve new_balance gerekli."}

    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == user_id,
    ).first()
    if not account:
        return {"success": False, "message": f"Hesap bulunamadi: id={account_id}"}

    # MC1 KORUMA — Emanet hesaba dokunma
    if account.is_emanet:
        return {
            "success": False,
            "message": f"'{account.name}' emanet hesap (MC1). Bakiye degistirilemez.",
        }

    old_balance = account.balance
    account.balance = float(new_balance)
    account.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "account_id": account.id,
        "account_name": account.name,
        "old_balance": old_balance,
        "new_balance": account.balance,
        "diff": round(account.balance - old_balance, 2),
    }


def _execute_add_transaction(db: Session, user_id: int, payload: Dict) -> Dict:
    """
    İşlem ekle (gelir/gider).
    Payload: {
        "transaction_type": "income"|"expense"|"transfer",
        "amount": float,
        "category": str?,
        "description": str?,
        "transaction_date": "YYYY-MM-DD"?,
        "account_id": int?,
        "is_card_expense": bool?,
        "auto_update_balance": bool?  # True ise hesap bakiyesi de güncellenir
    }
    """
    txn_type = payload.get("transaction_type")
    amount = payload.get("amount")
    if txn_type not in ("income", "expense", "transfer") or amount is None:
        return {"success": False, "message": "transaction_type ve amount gerekli."}

    txn_date = payload.get("transaction_date")
    if txn_date:
        txn_date = date.fromisoformat(txn_date) if isinstance(txn_date, str) else txn_date
    else:
        txn_date = date.today()

    account_id = payload.get("account_id")
    account_name = None  # BUG #031 fix
    if account_id:
        account = db.query(Account).filter(
            Account.id == account_id,
            Account.user_id == user_id,
        ).first()
        if not account:
            return {"success": False, "message": f"Hesap bulunamadi: id={account_id}"}
        if account.is_emanet:
            return {"success": False, "message": f"'{account.name}' emanet hesap (MC1)."}
        account_name = account.name  # BUG #031 fix

    txn = Transaction(
        user_id=user_id,
        account_id=account_id,
        transaction_type=TransactionType(txn_type),
        amount=float(amount),
        category=payload.get("category"),
        description=payload.get("description"),
        transaction_date=txn_date,
        is_card_expense=bool(payload.get("is_card_expense", False)),
    )
    db.add(txn)

    # Bakiye otomatik güncellensin mi?
    balance_diff = 0.0
    if payload.get("auto_update_balance") and account_id:
        if txn_type == "income":
            # BUG #103 fix: karta gelen gelir (iade/cashback/chargeback) BORCU AZALTIR;
            # nakit/yatırıma gelen gelir varlığı artırır. Eskiden kart için de += yapıp
            # borcu YANLIŞLIKLA artırıyordu (gider'in simetriği eksikti).
            if account.account_type == AccountType.credit_card:
                account.balance -= float(amount)  # kart borcu azalır
                balance_diff = -float(amount)
            else:
                account.balance += float(amount)
                balance_diff = float(amount)
        elif txn_type == "expense":
            # Kart harcamasıysa kart borcunu artır, nakitse nakti azalt
            if account.account_type == AccountType.credit_card:
                account.balance += float(amount)  # Kart borcu büyür
                balance_diff = float(amount)
            else:
                account.balance -= float(amount)
                balance_diff = -float(amount)
        account.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(txn)

    return {
        "success": True,
        "transaction_id": txn.id,
        "transaction_type": txn_type,
        "amount": txn.amount,
        "category": txn.category,
        "account_name": account_name,  # BUG #031 fix
        "balance_diff": balance_diff,
    }


def _execute_mark_debt_paid(db: Session, user_id: int, payload: Dict) -> Dict:
    """
    Kişisel borç/alacağı ödendi olarak işaretle.
    Payload: {"debt_id": int, "paid_date": "YYYY-MM-DD"?}
    """
    debt_id = payload.get("debt_id")
    if debt_id is None:
        return {"success": False, "message": "debt_id gerekli."}

    debt = db.query(PersonalDebt).filter(
        PersonalDebt.id == debt_id,
        PersonalDebt.user_id == user_id,
    ).first()
    if not debt:
        return {"success": False, "message": f"Borc kaydi bulunamadi: id={debt_id}"}

    if debt.is_paid:
        return {"success": False, "message": "Bu borc zaten odenmiş olarak isaretli."}

    paid_date_str = payload.get("paid_date")
    debt.paid_date = (
        date.fromisoformat(paid_date_str) if paid_date_str else date.today()
    )
    debt.is_paid = True

    # BUG #113 fix (kapsam-güdümlü keşif): mark_debt_paid TEK aksiyondur (prompt: "X bana ödedi
    # / borcumu ödedim" → mark_debt_paid). Bu yüzden NAKDİ DE HAREKET ETTİRMELİ — eskiden yalnız
    # is_paid işaretleyip nakdi hareketsiz bırakıyordu: alacak tahsili net değeri YANLIŞ düşürüyor,
    # borç ödemesi yanlış yükseltiyordu (tahsilat/ödeme net-nötr olmalı; görülen nakit değişmeli).
    # Simülasyon zaten böyle yapıyordu → executor ile TUTARLI hale geldi. Varsayılan nakit hesaba işlenir.
    cash = (
        db.query(Account)
        .filter(Account.user_id == user_id, Account.account_type == AccountType.cash)
        .order_by(Account.id.asc())
        .first()
    )
    cash_effect = 0.0
    if cash:
        if debt.direction == DebtDirection.receivable:
            cash.balance += debt.amount          # alacak TAHSİL edildi → nakit artar
            cash_effect = debt.amount
        else:
            cash.balance -= debt.amount          # borç ÖDENDİ → nakit azalır
            cash_effect = -debt.amount
        cash.updated_at = datetime.utcnow()

    db.commit()

    return {
        "success": True,
        "debt_id": debt.id,
        "counterparty": debt.counterparty,
        "amount": debt.amount,
        "direction": debt.direction.value,
        "paid_date": debt.paid_date.isoformat(),
        "cash_effect": cash_effect,               # +tahsilat / -ödeme; nakit hesap yoksa 0
        "cash_account": cash.name if cash else None,
    }


def _execute_sell_investment(db: Session, user_id: int, payload: Dict) -> Dict:
    """
    Yatırım fonu satışı — lot azalt, nakte ekle.
    Payload: {
        "investment_id": int,
        "lots_to_sell": float,
        "actual_price": float?,         # gerçekleşme fiyatı; verilmezse current_price
        "credit_to_account_id": int?,   # nakdin hangi hesaba geçeceği
    }

    MC1 KORUMA: Emanet hesap satılamaz.
    """
    inv_id = payload.get("investment_id")
    lots = payload.get("lots_to_sell")
    if inv_id is None or lots is None:
        return {"success": False, "message": "investment_id ve lots_to_sell gerekli."}

    inv = db.query(Account).filter(
        Account.id == inv_id,
        Account.user_id == user_id,
    ).first()
    if not inv:
        return {"success": False, "message": f"Yatirim bulunamadi: id={inv_id}"}
    if inv.account_type != AccountType.investment:
        return {"success": False, "message": f"'{inv.name}' yatirim hesabi degil."}

    # MC1 — KIRMIZI ÇİZGİ — EMANET DOKUNULMAZ
    if inv.is_emanet:
        return {
            "success": False,
            "message": (
                f"'{inv.name}' emanet hesap (MC1 - Master Checkpoint #1). "
                f"Hicbir senaryoda satilamaz. Bu aksiyon REDDEDILDI."
            ),
        }

    lots = float(lots)
    if lots <= 0:
        return {"success": False, "message": "lots_to_sell sifirdan buyuk olmali."}
    if lots > (inv.lot_count or 0):
        return {
            "success": False,
            "message": f"Yetersiz lot. Mevcut: {inv.lot_count}, satilmak istenen: {lots}",
        }
    if inv.cost_per_lot is None or inv.current_price is None:
        return {
            "success": False,
            "message": "cost_per_lot veya current_price eksik — satis simulasyonu yapilamaz.",
        }

    actual_price = float(payload.get("actual_price") or inv.current_price)

    # Stopaj hesabı (Rules Engine'i kullanıyoruz — LLM hesaplamasın)
    sim = simulate_partial_sale(
        lot_count=inv.lot_count,
        cost_per_lot=inv.cost_per_lot,
        current_price=actual_price,
        lots_to_sell=lots,
    )

    # BUG #068 fix (AE-002): Satış gelirinin gideceği hesabı MUTASYONDAN ÖNCE doğrula.
    # Eskiden lot düşürülüp commit ediliyor, ama hesap geçersiz/emanet/eksikse
    # net_eline_gecen hiçbir yere yatmadan "success" dönüyordu → para sessizce yok oluyordu.
    credit_account_id = payload.get("credit_to_account_id")
    if not credit_account_id:
        return {"success": False, "message": "Satış geliri için hedef nakit hesap (credit_to_account_id) belirtilmeli — aksi halde para kaybolur. Satış yapılmadı."}
    credit_account = db.query(Account).filter(
        Account.id == credit_account_id,
        Account.user_id == user_id,
    ).first()
    if credit_account is None:
        return {"success": False, "message": f"Nakit aktarılacak hesap bulunamadı: id={credit_account_id}. Satış yapılmadı."}
    if credit_account.is_emanet:
        return {"success": False, "message": f"'{credit_account.name}' emanet hesap — satış parası buraya yatırılamaz. Satış yapılmadı."}

    # Doğrulama geçti — şimdi mutasyon (lot azalt + nakdi hedefe yatır) tek commit'te
    inv.lot_count = sim["kalan_lot"]
    inv.balance = sim["kalan_deger"]
    # BUG #102 fix: kalan_deger = kalan_lot * actual_price. actual_price taze bir piyasa
    # gözlemidir; current_price'ı da güncelle ki balance == lot_count*current_price tutarlı
    # kalsın. Eskiden current_price bayat kalıp cockpit (lot*current_price) ile balance ve
    # simülasyon (balance okur) birbirinden sapıyordu.
    inv.current_price = actual_price
    inv.last_price_update = datetime.utcnow()
    inv.updated_at = datetime.utcnow()
    credit_account.balance += sim["net_eline_gecen"]
    credit_account.updated_at = datetime.utcnow()

    db.commit()

    return {
        "success": True,
        "investment_id": inv.id,
        "investment_name": inv.name,
        "fund_code": inv.fund_code,
        "satis_simulasyonu": sim,
        "kalan_lot": inv.lot_count,
        "kalan_deger": inv.balance,
        "credit_account": (
            {"id": credit_account.id, "name": credit_account.name, "yeni_bakiye": credit_account.balance}
            if credit_account else None
        ),
    }


def _execute_update_fund_price(db: Session, user_id: int, payload: Dict) -> Dict:
    """
    Yatırım fiyatını manuel günceller (fund_tracker'ın propose üzerinden çalışan versiyonu).
    Payload: {"account_id": int, "new_price": float}
    """
    from app.fund_tracker import update_fund_price_manual
    account_id = payload.get("account_id")
    new_price = payload.get("new_price")
    if account_id is None or new_price is None:
        return {"success": False, "message": "account_id ve new_price gerekli."}

    return update_fund_price_manual(db, account_id, float(new_price))


def _execute_add_master_checkpoint(db: Session, user_id: int, payload: Dict) -> Dict:
    """
    Yeni Master Checkpoint ekler.
    Payload: {
        "title": str,
        "description": str,
        "checkpoint_type": "red_line"|"strategy"|"rule"|"context",
        "priority": int (1-3)
    }
    """
    title = payload.get("title")
    desc = payload.get("description")
    cp_type = payload.get("checkpoint_type")
    priority = payload.get("priority", 2)

    if not title or not desc or not cp_type:
        return {"success": False, "message": "title, description, checkpoint_type gerekli."}

    try:
        cp_type_enum = CheckpointType(cp_type)
    except ValueError:
        return {
            "success": False,
            "message": f"Gecersiz checkpoint_type: {cp_type}. red_line|strategy|rule|context olabilir.",
        }

    cp = MasterCheckpoint(
        user_id=user_id,
        title=title,
        description=desc,
        checkpoint_type=cp_type_enum,
        priority=int(priority),
        is_active=True,
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)

    return {
        "success": True,
        "checkpoint_id": cp.id,
        "title": cp.title,
        "type": cp.checkpoint_type.value,
        "priority": cp.priority,
    }