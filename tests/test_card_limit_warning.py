"""
BUG #027 — kart limit aşımı uyarısı (deterministik).

propose_action bir kart giderini limitin üstüne taşıyacaksa DB'yi REDDETMEZ (kullanıcı
karar verir) ama pending'e bir `warning` / `_warning_text` iliştirir. Murat'ın kartı
gerçek hayatta ~%99.8 dolu olduğundan bu sinyal sürekli tetiklenir — davranışı kilitliyoruz.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, Account, AccountType
from app.action_executor import propose_action


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, name="murat"))
    # limite çok yakın kart: 11.800 / 12.000
    session.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                        balance=11800.0, credit_limit=12000.0))
    session.commit()
    yield session
    session.close()


def _propose(session, amount, category="yemek"):
    # user_message=None → HESAP_BELIRSIZ guard atlanır; "yemek" kart kategorisi olduğundan
    # normalize kartı account_id yapar ve is_card_expense=True set eder.
    return propose_action(
        db=session, user_id=1, action_type="add_transaction",
        payload={"amount": amount, "transaction_type": "expense", "category": category},
        summary=f"{amount} TL {category}",
    )


def test_limit_asiminda_uyari_iliştirilir(db):
    pending = _propose(db, 500)     # 11.800 + 500 = 12.300 > 12.000 → 300 TL aşım
    assert pending._warning_text is not None
    assert "aşacak" in pending._warning_text
    assert pending.warning == pending._warning_text   # DB alanı da yazılmış


def test_limit_altinda_uyari_yok(db):
    pending = _propose(db, 100)     # 11.800 + 100 = 11.900 < 12.000 → uyarı yok
    assert pending._warning_text is None
    assert pending.warning is None


def test_tam_limitte_uyari_yok(db):
    pending = _propose(db, 200)     # 11.800 + 200 = 12.000 == limit → aşım YOK (> katı)
    assert pending._warning_text is None
