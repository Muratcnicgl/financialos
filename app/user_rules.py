"""
Kullanıcı-tanımlı kural motoru (P3.5 / H3, BUG #192).

**Sorun (Murat, 4 Ağu):** Sistem "giriş yapılabilen Murat'ın OS'u"ydu. Kod içinde MC1 gibi
SABİT kurallar vardı (`is_emanet` hesabı satılamaz) ve bunlar gerçekten **kod seviyesinde**
dayatılıyordu; ama kullanıcının kendi yazdığı kırmızı çizgi ("acil fonuma dokunmam") yalnızca
koça **tavsiye** olarak gidiyordu — yani LLM'in iyi niyetine kalmıştı. ADR-001'in ruhu
("kural motoru karar verir, LLM açıklar") kullanıcının KENDİ kuralları için geçerli değildi.

**Karar:** kurallar VERİ olarak saklanır (`MasterCheckpoint.rule_type` + `rule_params`) ve
aksiyon uygulanmadan ÖNCE burada değerlendirilir. İhlalde işlem **bloklanır** ve kullanıcıya
KENDİ kuralının başlığıyla açıklanır. Bu, sektörde "rules as data" / policy-engine desenidir;
ürün tarafında YNAB'ın "kuralı zorla" felsefesine yakın, Monarch'ın "yumuşak hedef"ine uzaktır
— fark: kuralı ürün değil, KULLANICI yazar.

Desteklenen kural tipleri (hepsi opsiyonel; serbest metin kırmızı çizgiler eskisi gibi çalışır):
  - `min_cash_floor`      {"amount": 5000}      → toplam nakit bu tutarın altına düşemez
  - `account_untouchable` {"account_id": 3}     → o hesabın bakiyesi değiştirilemez
  - `max_single_expense`  {"amount": 2500}      → tek seferde bu tutarın üstünde harcama yapılamaz

Yeni tip eklemek: `_DEGERLENDIRICILER`'e bir fonksiyon ekle + `RULE_TYPES`'a yaz + test.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models import Account, AccountType, MasterCheckpoint
from app.money import D

logger = logging.getLogger(__name__)

# Kullanıcıya (ve API doğrulamasına) açık tip listesi — tek kaynak.
RULE_TYPES = ("min_cash_floor", "account_untouchable", "max_single_expense")


class RuleViolation(Exception):
    """Kullanıcının kendi kuralı ihlal edildi. Mesaj KULLANICININ kural başlığını taşır."""

    def __init__(self, checkpoint_title: str, aciklama: str):
        self.checkpoint_title = checkpoint_title
        self.aciklama = aciklama
        super().__init__(f"'{checkpoint_title}' kuralın engelledi: {aciklama}")


# ──────────────────────────────────────────────────────────────────────────────
# Aksiyon → etki çıkarımı (kural motoru saf: DB okur, yazmaz — ADR-001)
# ──────────────────────────────────────────────────────────────────────────────

def _nakit_toplami(db: Session, user_id: int, workspace_id: Optional[int]) -> Decimal:
    from app.workspace_deps import scope_filter
    satirlar = (db.query(Account.balance)
                .filter(scope_filter(Account, user_id, workspace_id),
                        Account.account_type == AccountType.cash)
                .all())
    return sum((D(r[0]) for r in satirlar), D(0))


def _harcama_tutari(action_type: str, payload: dict) -> Decimal:
    """Aksiyonun NAKİT AZALTICI tutarı (yoksa 0). Pozitif = nakit çıkışı."""
    if action_type == "add_transaction":
        if payload.get("transaction_type") != "expense":
            return D(0)
        if payload.get("is_card_expense"):
            return D(0)  # kart harcaması nakdi hemen azaltmaz
        return abs(D(payload.get("amount", 0)))
    if action_type in ("pay_debt", "mark_debt_paid", "pay_card", "pay_loan_installment"):
        return abs(D(payload.get("amount", 0)))
    return D(0)


def _etkilenen_hesap_id(payload: dict) -> Optional[int]:
    for anahtar in ("account_id", "target_account_id", "credit_account_id", "from_account_id"):
        deger = payload.get(anahtar)
        if isinstance(deger, int):
            return deger
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Kural değerlendiricileri
# ──────────────────────────────────────────────────────────────────────────────

def _min_cash_floor(db, user_id, workspace_id, action_type, payload, params) -> Optional[str]:
    taban = D(params.get("amount", 0))
    if taban <= 0:
        return None
    cikis = _harcama_tutari(action_type, payload)
    if cikis <= 0:
        return None
    mevcut = _nakit_toplami(db, user_id, workspace_id)
    sonra = mevcut - cikis
    if sonra < taban:
        return (f"bu işlem sonrası nakit {sonra:,.2f} TL olurdu; kendi belirlediğin taban "
                f"{taban:,.2f} TL")
    return None


def _account_untouchable(db, user_id, workspace_id, action_type, payload, params) -> Optional[str]:
    korunan = params.get("account_id")
    if not isinstance(korunan, int):
        return None
    if _etkilenen_hesap_id(payload) == korunan:
        from app.workspace_deps import scope_filter
        hesap = (db.query(Account)
                 .filter(Account.id == korunan,
                         scope_filter(Account, user_id, workspace_id))
                 .first())
        ad = hesap.name if hesap else f"#{korunan}"
        return f"'{ad}' hesabını dokunulmaz olarak işaretlemiştin"
    return None


def _max_single_expense(db, user_id, workspace_id, action_type, payload, params) -> Optional[str]:
    tavan = D(params.get("amount", 0))
    if tavan <= 0 or action_type != "add_transaction":
        return None
    if payload.get("transaction_type") != "expense":
        return None
    tutar = abs(D(payload.get("amount", 0)))
    if tutar > tavan:
        return (f"{tutar:,.2f} TL tek seferlik harcama, kendi koyduğun "
                f"{tavan:,.2f} TL sınırının üstünde")
    return None


_DEGERLENDIRICILER: dict[str, Callable] = {
    "min_cash_floor": _min_cash_floor,
    "account_untouchable": _account_untouchable,
    "max_single_expense": _max_single_expense,
}


# ──────────────────────────────────────────────────────────────────────────────
# Genel kapı — action_executor buradan geçer
# ──────────────────────────────────────────────────────────────────────────────

def enforce_user_rules(db: Session, user_id: int, action_type: str, payload: dict,
                       workspace_id: Optional[int] = None) -> None:
    """Kullanıcının aktif yapılandırılmış kurallarını dayatır. İhlalde `RuleViolation`.

    Serbest metin kırmızı çizgiler (rule_type=None) burada DEĞERLENDİRİLMEZ — onlar koça
    bağlam olarak gider. Yapılandırılmış kural yazan kullanıcı, kod seviyesinde korunur.
    """
    from app.workspace_deps import scope_filter

    kurallar = (db.query(MasterCheckpoint)
                .filter(scope_filter(MasterCheckpoint, user_id, workspace_id),
                        MasterCheckpoint.is_active.is_(True),
                        MasterCheckpoint.rule_type.isnot(None))
                .order_by(MasterCheckpoint.priority.asc(), MasterCheckpoint.id.asc())
                .all())

    for kural in kurallar:
        degerlendirici = _DEGERLENDIRICILER.get(kural.rule_type or "")
        if degerlendirici is None:
            # Bilinmeyen tip (ileri sürümden kalma veri) — sessizce ATLAMA, log'la.
            logger.warning("[user_rules] bilinmeyen kural tipi %r (checkpoint=%s)",
                           kural.rule_type, kural.id)
            continue
        try:
            params = json.loads(kural.rule_params) if kural.rule_params else {}
        except (json.JSONDecodeError, TypeError):
            logger.warning("[user_rules] bozuk rule_params (checkpoint=%s) — atlandı", kural.id)
            continue
        aciklama = degerlendirici(db, user_id, workspace_id, action_type, payload, params)
        if aciklama:
            raise RuleViolation(kural.title, aciklama)
