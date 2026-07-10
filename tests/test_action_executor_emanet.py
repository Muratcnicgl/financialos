"""
Master Checkpoint (MC1 — Emanet) enforcement + sell_investment para-güvenliği testleri.

GÜVENLİK-KRİTİK: PROJE.md "Master Checkpoint enforcement kod seviyesinde uygulanır" der.
Bu test o kuralın regresyona uğramadığını garanti eder (emanet hesap ASLA satılamaz),
ve BUG #068 (P0-2) fix'ini doğrular: geçersiz/emanet hedef hesapta satış parası kaybolmaz
ve lot düşmez.

İzolasyon: kendi in-memory SQLite engine'ini kurar (paylaşılan conftest'e / canlı DB'ye
DOKUNMAZ) — TEST-005/012 deseninin doğru hali.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models  # noqa: F401 — tabloların Base.metadata'ya kaydı
from app.models import Account, AccountType, User
from app.action_executor import _execute_sell_investment


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    yield session
    session.close()


def _seed(db):
    db.add(User(id=1, name="T"))
    db.add(Account(id=10, user_id=1, name="TLY", account_type=AccountType.investment,
                   balance=30.0, is_emanet=False, lot_count=6.0, cost_per_lot=3.616, current_price=5.0))
    db.add(Account(id=20, user_id=1, name="Nakit", account_type=AccountType.cash,
                   balance=1000.0, is_emanet=False))
    db.add(Account(id=30, user_id=1, name="Emanet Nakit", account_type=AccountType.cash,
                   balance=500.0, is_emanet=True))
    db.commit()


def test_gecerli_satis_nakit_yatar_lot_azalir(db):
    _seed(db)
    r = _execute_sell_investment(db, 1, {"investment_id": 10, "lots_to_sell": 4, "credit_to_account_id": 20})
    assert r["success"] is True
    assert db.get(Account, 10).lot_count == 2.0
    assert db.get(Account, 20).balance > 1000.0


def test_emanet_hedef_hesap_para_kaybolmaz_lot_kalir(db):
    """BUG #068 (P0-2): emanet hedef → başarısız, lot düşmez, para kaybolmaz."""
    _seed(db)
    r = _execute_sell_investment(db, 1, {"investment_id": 10, "lots_to_sell": 4, "credit_to_account_id": 30})
    assert r["success"] is False
    assert db.get(Account, 10).lot_count == 6.0


def test_gecersiz_hedef_hesap_lot_kalir(db):
    _seed(db)
    r = _execute_sell_investment(db, 1, {"investment_id": 10, "lots_to_sell": 4, "credit_to_account_id": 999})
    assert r["success"] is False
    assert db.get(Account, 10).lot_count == 6.0


def test_hedefsiz_satis_reddedilir(db):
    _seed(db)
    r = _execute_sell_investment(db, 1, {"investment_id": 10, "lots_to_sell": 4})
    assert r["success"] is False
    assert db.get(Account, 10).lot_count == 6.0


def test_MC1_emanet_yatirim_satilamaz(db):
    """Master Checkpoint #1: emanet YATIRIM hesabı hiçbir senaryoda satılamaz."""
    _seed(db)
    db.add(Account(id=40, user_id=1, name="Emanet Fon", account_type=AccountType.investment,
                   balance=100.0, is_emanet=True, lot_count=10.0, cost_per_lot=5.0, current_price=6.0))
    db.commit()
    r = _execute_sell_investment(db, 1, {"investment_id": 40, "lots_to_sell": 2, "credit_to_account_id": 20})
    assert r["success"] is False
    assert "emanet" in r["message"].lower()
    assert db.get(Account, 40).lot_count == 10.0  # dokunulmadı
