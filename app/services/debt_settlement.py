"""
BUG #241 — BORÇ/ALACAK KAPANIŞININ NAKİT AYAĞI: TEK DOĞRULUK KAYNAĞI.

Kullanıcı bildirimi (6 Ağu 2026): *"bir alacağı 'ödendi' işaretledim ama cockpit'te bakiyem
artmadı."* Aynı gerçek-dünya olayının (bir alacağın tahsili / bir borcun ödenmesi)
İKİ kod yolu vardı ve sözleşmeleri ayrışmıştı:

- koç yolu (`action_executor._execute_mark_debt_paid`, BUG #113) nakdi hareket ettiriyordu,
- panel yolu (`PUT /api/debts/{id}` — "Ödendi" butonu) yalnız `is_paid` bayrağını çeviriyordu.

Panelden tahsil işaretlenen alacak listeden düşüyor, karşılığı nakde geçmiyordu → **Tam Net
Değer tahsilatta düşüyor, borç ödemesinde yükseliyordu** (para buharlaşıyor/üretiliyor).
BUG #161/SBN-001 ailesinin aynısı: *işaret kuralı birden çok yerde ayrı kodlanmış.*
`balance_rules.balance_delta` transaction→bakiye işaretini nasıl tek yere topladıysa, bu
modül de borç/alacak kapanışı→nakit ayağını tek yere toplar; iki yol da buradan geçer.

## Sözleşme
- Etki YÖNÜ: `receivable` (tahsilat) → nakit **+amount**, `payable` (ödeme) → nakit **−amount**.
- Etki, kaydın `settlement_account_id` alanında **iz bırakır**. Bu alan aynı zamanda "nakit
  ayağı uygulandı mı" işaretidir: NULL ise ayak hiç uygulanmamıştır (fix öncesi panelden
  işaretlenmiş eski kayıtlar böyledir) ve geri alma o kayıttan para DÜŞMEZ (hayalet para yok).
- Kapanış her mutasyonda yeniden senkronlanır: `delta = yeni_etki − eski_etki`. Böylece
  işaretle/geri al/tutar düzelt yollarının hepsi tek uygulamalıdır (çift-sayım imkânsız).
- Hedef hesap: `app/account_rules.varsayilan_nakit_hesap` — kapsamdaki (workspace) ilk
  **emanet olmayan** nakit hesap. Emanet dışlaması MC1 zorunluluğu; hesap seçimi de sınıf
  taramasında tek kaynağa toplandı (5 ayrı seçici vardı, hiçbiri emaneti dışlamıyordu).
- Nakit hesap yoksa kayıt yine ödendi işaretlenir, ayak uygulanmaz (`settlement_account_id`
  NULL kalır) — istek patlamaz, sessiz yanlış bakiye de üretilmez.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.account_rules import varsayilan_nakit_hesap
from app.models import Account, PersonalDebt
from app.money import D, ZERO


def kapanis_delta(direction, amount) -> Decimal:
    """Bir borç/alacak kapanışının NAKDE etkisi (işaret konvansiyonu TEK KAYNAK)."""
    yon = direction.value if hasattr(direction, "value") else direction
    amt = D(amount or 0)
    if yon == "receivable":
        return amt      # alacak TAHSİL edildi → nakit artar
    if yon == "payable":
        return -amt     # borç ÖDENDİ → nakit azalır
    return ZERO


@dataclass(frozen=True)
class KapanisDurumu:
    """Nakit ayağını belirleyen alanların anlık görüntüsü (mutasyon ÖNCESİ okunur)."""
    is_paid: bool
    amount: Decimal
    direction: str
    settlement_account_id: Optional[int]

    @classmethod
    def oku(cls, debt: PersonalDebt) -> "KapanisDurumu":
        yon = debt.direction.value if hasattr(debt.direction, "value") else debt.direction
        return cls(
            is_paid=bool(debt.is_paid),
            amount=D(debt.amount or 0),
            direction=yon,
            settlement_account_id=debt.settlement_account_id,
        )


def senkronize_nakit(
    db: Session,
    user_id: int,
    debt: PersonalDebt,
    onceki: KapanisDurumu,
    workspace_id: Optional[int] = None,
) -> dict:
    """Kaydın GÜNCEL hâline göre nakit ayağını senkronlar (fark kadar uygular).

    `db.commit()` ÇAĞIRMAZ — çağıran, borç mutasyonuyla aynı transaction'da commit eder
    (yarı uygulanmış kapanış olamaz). Döner: `{"cash_effect", "cash_account", "applied"}`.
    """
    yeni_etki = kapanis_delta(debt.direction, debt.amount) if debt.is_paid else ZERO

    # Geri sarma YALNIZCA ayağın gerçekten işlendiği hesaptan yapılır. Kayıtta iz yoksa
    # (NULL) ayak hiç uygulanmamıştır → geri sarılacak bir şey de yoktur (hayalet para yok).
    # Varsayılan hesap çözümlemesine DÜŞÜLMEZ: iz, "nereye" sorusunun tek cevabıdır.
    eski_hesap: Optional[Account] = (
        # scope-exempt: id İSTEMCİDEN GELMEZ — kaydın kendi `settlement_account_id` izidir ve
        # o iz kapsamlı bir çözümleyiciyle (account_rules) yazılmıştır. Kullanıcı bu alanı
        # set edemez (DebtUpdate şemasında yok), dolayısıyla başka kapsama işaret edemez.
        db.get(Account, onceki.settlement_account_id)
        if (onceki.is_paid and onceki.settlement_account_id is not None)
        else None
    )
    eski_etki = (
        kapanis_delta(onceki.direction, onceki.amount) if eski_hesap is not None else ZERO
    )

    hedef: Optional[Account] = None
    if yeni_etki != ZERO:
        # Ayak zaten uygulanmışsa AYNI hesaba yaz (hesap listesi değişse bile simetri korunur).
        if onceki.settlement_account_id is not None:
            # scope-exempt: id kaydın kendi izinden gelir (istemci set edemez) — yukarıdaki
            # geri-sarma gerekçesiyle aynı; aynı hesaba yazmak simetrinin ta kendisidir.
            hedef = db.get(Account, onceki.settlement_account_id)
        if hedef is None:
            hedef = varsayilan_nakit_hesap(db, user_id, workspace_id)
        if hedef is None:
            yeni_etki = ZERO        # nakit hesap yok → ayak uygulanamaz

    simdi = datetime.utcnow()
    if eski_hesap is not None and hedef is not None and eski_hesap.id == hedef.id:
        fark = yeni_etki - eski_etki
        if fark != ZERO:
            hedef.balance = D(hedef.balance) + fark
            hedef.updated_at = simdi
    else:
        if eski_hesap is not None and eski_etki != ZERO:
            eski_hesap.balance = D(eski_hesap.balance) - eski_etki
            eski_hesap.updated_at = simdi
        if hedef is not None and yeni_etki != ZERO:
            hedef.balance = D(hedef.balance) + yeni_etki
            hedef.updated_at = simdi

    debt.settlement_account_id = hedef.id if yeni_etki != ZERO else None

    return {
        "cash_effect": yeni_etki - eski_etki,        # bu istekte nakde giden net hareket
        "cash_account": hedef.name if hedef is not None else None,
        "applied": yeni_etki != ZERO,
    }
