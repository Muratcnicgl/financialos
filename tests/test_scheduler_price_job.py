"""
Scheduler fiyat job'ı testi (M4 / ADR-029). Ağ + canlı DB YOK: SessionLocal izole
in-memory'ye, fetch_for_account stub'a monkeypatch'lenir. Job'ın TÜM yatırım hesaplarını
güncellediği + nakit/kredi hesaplara dokunmadığı doğrulanır.
"""
import asyncio

from decimal import Decimal

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import scheduler, price_providers
from app.models import Base, User, Account, AccountType, PriceHistory, PriceSource


def _make_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), engine


def test_job_updates_all_investment_accounts(monkeypatch):
    Session, engine = _make_session_factory()
    seed = Session()
    u = User(name="test_user")
    seed.add(u)
    seed.commit()
    seed.add_all([
        Account(user_id=u.id, name="TLY Kisisel", account_type=AccountType.investment,
                balance=1000.0, fund_code="TLY"),
        Account(user_id=u.id, name="TLY Emanet", account_type=AccountType.investment,
                balance=2000.0, fund_code="TLY", is_emanet=True),
        Account(user_id=u.id, name="Kasa", account_type=AccountType.cash, balance=50.0),
    ])
    seed.commit()
    seed.close()

    # SessionLocal → izole in-memory; fetch → stub (ağ yok)
    monkeypatch.setattr(scheduler, "SessionLocal", Session)
    monkeypatch.setattr(price_providers, "fetch_for_account",
                        lambda acc: (Decimal("7277.9040"), PriceSource.TEFAS.value))

    asyncio.run(scheduler.fetch_investment_prices_job())

    check = Session()
    invs = check.query(Account).filter(Account.account_type == AccountType.investment).all()
    assert len(invs) == 2
    for a in invs:
        assert float(a.current_price) == pytest.approx(7277.904)  # ADR-030: current_price Numeric(Decimal)
        assert a.last_price_update is not None
    # nakit dokunulmadı
    cash = check.query(Account).filter(Account.account_type == AccountType.cash).first()
    assert cash.current_price is None
    # PriceHistory: iki hesap aynı fon → tek kompozit-PK satır (idempotent)
    rows = check.query(PriceHistory).all()
    assert len(rows) == 1
    assert rows[0].close_price == Decimal("7277.9040")
    check.close()


def test_job_survives_fetch_failure(monkeypatch):
    """Bir hesabın fiyatı çekilemese (None) job çökmez, diğerlerini işler."""
    Session, engine = _make_session_factory()
    seed = Session()
    u = User(name="test_user")
    seed.add(u)
    seed.commit()
    seed.add_all([
        Account(user_id=u.id, name="Iyi Fon", account_type=AccountType.investment,
                balance=1000.0, fund_code="TLY"),
        Account(user_id=u.id, name="Kotu Fon", account_type=AccountType.investment,
                balance=1000.0, fund_code="ZZZ"),
    ])
    seed.commit()
    seed.close()

    def flaky(acc):
        if acc.fund_code == "ZZZ":
            return None  # çekilemedi
        return (Decimal("10.0"), PriceSource.TEFAS.value)

    monkeypatch.setattr(scheduler, "SessionLocal", Session)
    monkeypatch.setattr(price_providers, "fetch_for_account", flaky)

    asyncio.run(scheduler.fetch_investment_prices_job())  # exception yok

    check = Session()
    good = check.query(Account).filter(Account.fund_code == "TLY").first()
    bad = check.query(Account).filter(Account.fund_code == "ZZZ").first()
    assert float(good.current_price) == pytest.approx(10.0)
    assert bad.current_price is None  # çekilemeyen dokunulmadı
    check.close()
