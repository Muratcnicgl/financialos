"""
BUG #241 sınıf taraması (L11) — VARSAYILAN HESAP SEÇİMİ: TEK DOĞRULUK KAYNAĞI.

`balance_rules.py` bir işlemin bakiyeye ETKİSİNİ (işaret) tek yere topladı; bu modül de
"hangi hesaba" sorusunu tek yere toplar. Kullanıcı hesap belirtmediğinde parayı bir yere
yazan beş yol vardı ve **beşi de kendi sorgusunu yazıyordu**:

    action_executor._execute_mark_debt_paid · _execute_pay_credit_card ·
    routers/transactions._normalize (hesapsız işlem) · routers/incomes.trigger-due ·
    simulation_engine._find_default_cash_account

Hiçbiri **emanet** hesabı dışlamıyordu (MC1: emanet bakiyesine otomatik hiçbir yol
dokunamaz) ve üçü sırasızdı (`\\.first()` — DB'nin döndürdüğü ilk satır; hesap ekleyip
silmek varsayılanı sessizce değiştirebilir, aynı olay iki kez farklı hesaba düşebilir).
Yani MC1 zorunluluğu "hesabı kim seçerse" kuralına bağlıydı; seçici çoğalınca kural
delinir. Kapı: `tests/test_varsayilan_hesap_kapisi.py`.

Sözleşme: kapsam (workspace) içinde, **emanet olmayan**, istenen tipteki **en küçük id'li**
hesap. Deterministik olması şart — bir kapanışın uygulanması ve geri sarılması aynı hesabı
bulmalı (BUG #241 simetrisi).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Account, AccountType
from app.workspace_deps import scope_filter


def varsayilan_hesap(
    db: Session,
    user_id: int,
    workspace_id: Optional[int] = None,
    *,
    tip: AccountType = AccountType.cash,
) -> Optional[Account]:
    """Kapsamdaki ilk (en küçük id'li) emanet-OLMAYAN `tip` hesabı; yoksa None."""
    return (
        db.query(Account)
        .filter(
            scope_filter(Account, user_id, workspace_id),
            Account.account_type == tip,
            Account.is_emanet.is_(False),   # MC1: emanet otomatik yolların hedefi olamaz
        )
        .order_by(Account.id.asc())
        .first()
    )


def varsayilan_nakit_hesap(
    db: Session, user_id: int, workspace_id: Optional[int] = None
) -> Optional[Account]:
    """Paranın gireceği/çıkacağı varsayılan NAKİT hesap (en sık kullanılan biçim)."""
    return varsayilan_hesap(db, user_id, workspace_id, tip=AccountType.cash)
