"""
fund_tracker kapsamı — fiyat güncelleme (BUG #115 sahiplik), tazelik, K/Z değeri.
Kapsam %14'tü; finansal hesap (balance = lot*fiyat) + user_id scoping burada test edilir.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType
from app.fund_tracker import (
    update_fund_price_manual, is_price_stale, get_price_age_text, get_freshness_summary,
)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add_all([User(id=1, name="murat"), User(id=2, name="baskasi")])
    s.commit()
    yield s
    s.close()


def _inv(db, user_id=1, **kw):
    a = Account(user_id=user_id, name="TLY", account_type=AccountType.investment,
                lot_count=10.0, cost_per_lot=800.0, current_price=1000.0, balance=10000.0, **kw)
    db.add(a); db.commit(); db.refresh(a)
    return a


def test_fiyat_guncelleme_balance_lot_carpar(db):
    inv = _inv(db)
    res = update_fund_price_manual(db, inv.id, 1200.0, user_id=1)
    assert res["success"] is True
    db.refresh(inv)
    assert inv.current_price == 1200.0
    assert inv.balance == 12000.0          # 10 lot * 1200
    assert res["value_diff"] == 2000.0


def test_115_baska_kullanici_fonunu_guncelleyemez(db):
    inv = _inv(db, user_id=1)
    res = update_fund_price_manual(db, inv.id, 1200.0, user_id=2)   # user 2, user 1'in fonu
    assert res["success"] is False
    assert "bulunamadi" in res["message"].lower()
    db.refresh(inv)
    assert inv.current_price == 1000.0     # dokunulmadı


def test_negatif_fiyat_reddedilir(db):
    inv = _inv(db)
    res = update_fund_price_manual(db, inv.id, -5.0, user_id=1)
    assert res["success"] is False


def test_yatirim_olmayan_hesap_reddedilir(db):
    cash = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=100.0)
    db.add(cash); db.commit(); db.refresh(cash)
    res = update_fund_price_manual(db, cash.id, 1200.0, user_id=1)
    assert res["success"] is False


def test_is_price_stale():
    assert is_price_stale(None) is True
    assert is_price_stale(datetime.utcnow()) is False
    assert is_price_stale(datetime.utcnow() - timedelta(days=5)) is True


def test_get_price_age_text_none():
    txt = get_price_age_text(None)
    assert isinstance(txt, str) and len(txt) > 0


def test_freshness_summary(db):
    _inv(db, user_id=1, last_price_update=datetime.utcnow())
    summary = get_freshness_summary(db, 1)
    assert isinstance(summary, dict)
