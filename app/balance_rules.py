"""
M53 (Wave-7) — İŞARET KONVANSİYONU TEK DOĞRULUK KAYNAĞI.

BUG #161 (kart ödemesi borcu artırıyordu) + SBN-001 (backfill_net_worth kredi/kart geçmiş net-değeri
yanlış) AYNI AİLE: bir transaction'ın bir hesabın bakiyesine etkisi (işaret) hesabın TİPİNE bağlı, ama bu
kural birden çok yerde AYRI kodlanmıştı (transactions._apply_to_balance + action_executor + backfill._balance_at
[YANLIŞ, tip-agnostik]). Bu modül o kuralı TEK YERE toplar; tüm bakiye/net-worth hesapları buradan geçer.

İşaret konvansiyonu (varlık pozitif, borç bakiyesi pozitif=borçlu):
- **cash** (varlık):        income → +amount,  expense → −amount
- **credit_card** (borç):   expense → +amount (harcama borcu artırır),  income → −amount (ödeme borcu azaltır)
- **loan** (borç):          expense → −amount (taksit borcu azaltır),   income → 0 (tanımsız, no-op)
- **investment/other:**     0 (bakiye transaction ile değişmez; fiyat güncellemesiyle değişir)

`balance_delta(account_type, txn_type, amount)` = reverse=False etkisi (Decimal). Geri-al (undo/backfill) = −delta.
"""
from __future__ import annotations

from decimal import Decimal
from app.money import D, ZERO


def _norm(x) -> str:
    return x.value if hasattr(x, "value") else x


def balance_delta(account_type, txn_type, amount) -> Decimal:
    """Bir transaction'ın hesap bakiyesine etkisi (işaret konvansiyonu TEK KAYNAK)."""
    atype = _norm(account_type)
    ttype = _norm(txn_type)
    amt = D(amount)

    if atype == "cash":
        if ttype == "income":
            return amt
        if ttype == "expense":
            return -amt
    elif atype == "credit_card":
        if ttype == "expense":
            return amt          # harcama borcu artırır
        if ttype == "income":
            return -amt         # ödeme borcu azaltır
    elif atype == "loan":
        if ttype == "expense":
            return -amt         # taksit borcu azaltır
        # loan + income: tanımsız → 0 (mevcut _apply_to_balance davranışı korunur)
    # investment/other veya transfer: bakiye transaction ile değişmez
    return ZERO


def net_worth_seen(cash, investment, card_debt, loan_debt) -> Decimal:
    """Görülen Net Değer (alacaksız, operasyonel) = nakit + yatırım − kart − kredi. TEK KAYNAK."""
    return D(cash) + D(investment) - D(card_debt) - D(loan_debt)


def net_worth_full(seen, receivables, payables=ZERO) -> Decimal:
    """Tam Net Değer (stratejik) = Görülen + kişisel alacaklar − kişisel borçlar. TEK KAYNAK."""
    return D(seen) + D(receivables) - D(payables)
