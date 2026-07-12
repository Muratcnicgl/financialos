"""
Fiyat sağlayıcı router + kayıt testleri (M4 / ADR-029). Ağ YOK — pytefas çağrısı
monkeypatch'lenir; kayıt/cache/dispatch mantığı izole in-memory DB'de doğrulanır.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app import price_providers
from app.price_providers import (
    fetch_for_account,
    get_fund_price,
    record_investment_price,
)
from app.models import Account, AccountType, PriceHistory, PriceSource


@pytest.fixture(autouse=True)
def _clear_cache():
    """Her test taze cache'le başlasın — testler arası sızıntı olmasın."""
    price_providers.router._CACHE.clear()
    yield
    price_providers.router._CACHE.clear()


def _investment_account(user_id: int, fund_code: str = "TLY", name: str = "TLY Fon") -> Account:
    return Account(
        user_id=user_id, name=name, account_type=AccountType.investment,
        balance=1000.0, fund_code=fund_code, lot_count=10.0,
    )


def test_record_writes_price_history_and_updates_cache(db_session, test_user):
    """record_investment_price → PriceHistory satırı + current_price denormalize + is_new=True."""
    acc = _investment_account(test_user.id)
    db_session.add(acc)
    db_session.commit()

    is_new = record_investment_price(db_session, acc, Decimal("7277.9040"), PriceSource.TEFAS.value)

    assert is_new is True
    assert acc.current_price == pytest.approx(7277.904)  # current_price Float denormalize cache
    assert acc.last_price_update is not None
    rows = db_session.query(PriceHistory).filter(PriceHistory.fund_code == "TLY").all()
    assert len(rows) == 1
    assert rows[0].close_price == Decimal("7277.9040")
    assert rows[0].price_date == date.today()
    assert rows[0].source == PriceSource.TEFAS.value


def test_record_is_idempotent_same_day_source(db_session, test_user):
    """Aynı gün+kaynak ikinci kayıt yeni satır AÇMAZ (ADR-012 kompozit PK); fiyatı günceller."""
    acc = _investment_account(test_user.id)
    db_session.add(acc)
    db_session.commit()

    assert record_investment_price(db_session, acc, Decimal("100.0"), PriceSource.TEFAS.value) is True
    assert record_investment_price(db_session, acc, Decimal("200.0"), PriceSource.TEFAS.value) is False

    rows = db_session.query(PriceHistory).filter(PriceHistory.fund_code == "TLY").all()
    assert len(rows) == 1  # tek satır kaldı
    assert rows[0].close_price == Decimal("200.0")  # üzerine yazıldı (close_price Numeric)
    assert acc.current_price == pytest.approx(200.0)  # current_price Float


def test_get_fund_price_caches_underlying_call(monkeypatch):
    """İki get_fund_price aynı fon+gün için alt pytefas çağrısını TEK kez yapar (TTL cache)."""
    calls = {"n": 0}

    def fake_fetch(code):
        calls["n"] += 1
        return Decimal("42.0")

    monkeypatch.setattr("app.fund_tracker.try_auto_fetch_fund_price", fake_fetch)

    r1 = get_fund_price("TLY")
    r2 = get_fund_price("TLY")

    assert r1 == (Decimal("42.0"), PriceSource.TEFAS.value)
    assert r2 == (Decimal("42.0"), PriceSource.TEFAS.value)
    assert calls["n"] == 1  # ikinci çağrı cache'den


def test_get_fund_price_none_when_unavailable(monkeypatch):
    monkeypatch.setattr("app.fund_tracker.try_auto_fetch_fund_price", lambda code: None)
    assert get_fund_price("TLY") is None
    assert get_fund_price("") is None  # boş kod


def test_fetch_for_account_dispatch(monkeypatch, db_session, test_user):
    """Yatırım+fund_code → fiyat döner; nakit/kod-yok hesap → None (dispatch doğru)."""
    monkeypatch.setattr("app.fund_tracker.try_auto_fetch_fund_price", lambda code: Decimal("9.0"))

    inv = _investment_account(test_user.id)
    cash = Account(user_id=test_user.id, name="Kasa", account_type=AccountType.cash, balance=5.0)
    inv_nocode = _investment_account(test_user.id, fund_code=None, name="Kodsuz")

    assert fetch_for_account(inv) == (Decimal("9.0"), PriceSource.TEFAS.value)
    assert fetch_for_account(cash) is None
    assert fetch_for_account(inv_nocode) is None
