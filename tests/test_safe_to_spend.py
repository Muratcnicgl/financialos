"""
FEAT-009 — "Harcanabilir güvenli tutar" (Safe-to-Spend, Copilot ilhamı).
guvenli_harcama = max(0, lowest_forecast_balance - buffer). Bugün X harcamak tüm gelecek
bakiyeleri X düşürür → güvenli tutar en düşük projekte bakiyeye eşittir. Deterministik.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, PersonalDebt, DebtDirection
from app.rules_engine import _calculate_safe_to_spend, generate_cockpit

TODAY = date(2026, 5, 1)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


def _cash(db, balance):
    a = Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=balance)
    db.add(a); db.commit(); db.refresh(a)
    return a


def _payable(db, amount, due_in_days):
    d = PersonalDebt(user_id=1, counterparty="Banka", direction=DebtDirection.payable,
                     amount=amount, is_paid=False, due_date=TODAY + timedelta(days=due_in_days))
    db.add(d); db.commit(); db.refresh(d)
    return d


# ---- saf fonksiyon ---------------------------------------------------------

def test_pure_summary_yoksa_sifir():
    assert _calculate_safe_to_spend(None) == 0.0


def test_pure_lowest_pozitif():
    assert _calculate_safe_to_spend({"lowest_balance": 3000.0}) == 3000.0


def test_pure_buffer_dususu():
    assert _calculate_safe_to_spend({"lowest_balance": 3000.0}, buffer=1000.0) == 2000.0


def test_pure_lowest_negatif_sifir():
    # düzenli akışı bile negatife düşen → güvenli harcama YOK
    assert _calculate_safe_to_spend({"lowest_balance": -500.0}) == 0.0


def test_pure_buffer_lowesttan_buyuk_sifir():
    assert _calculate_safe_to_spend({"lowest_balance": 500.0}, buffer=1000.0) == 0.0


# ---- generate_cockpit entegrasyonu ----------------------------------------

def test_cockpit_guvenli_harcama_alani_var(db):
    _cash(db, 5000.0)
    cockpit = generate_cockpit(1, TODAY, db)
    assert "guvenli_harcama" in cockpit


def test_cockpit_lumpy_borc_guvenli_tutari_kisitlar(db):
    """
    Nakit 5000 ama 20 gün sonra 4000 borç → en düşük projekte bakiye 1000 →
    güvenli harcama 1000 (nakit 5000 DEĞİL — lumpy yükümlülük tavanı düşürür).
    Bu daily_limit'ten daha güçlü ileriye-dönük sinyal.
    """
    _cash(db, 5000.0)
    _payable(db, 4000.0, 20)
    cockpit = generate_cockpit(1, TODAY, db)
    assert cockpit["guvenli_harcama"] == 1000.0


def test_cockpit_kriz_senaryosunda_sifir(db):
    """Nakit 1000, 10 gün sonra 3000 borç → en düşük −2000 → güvenli harcama 0 (realist)."""
    _cash(db, 1000.0)
    _payable(db, 3000.0, 10)
    cockpit = generate_cockpit(1, TODAY, db)
    assert cockpit["guvenli_harcama"] == 0.0


# ---- pure: kart-farkındalığı (BUG #123) ------------------------------------

def test_pure_kart_borcu_dususu():
    # lowest 4276 ama 11976 kart borcu → 4276-11976 < 0 → 0 (tehlikeli iyimserlik önlendi)
    assert _calculate_safe_to_spend({"lowest_balance": 4276.0}, kart_borcu=11976.0) == 0.0
    # küçük kart borcu → kısmi düşüş
    assert _calculate_safe_to_spend({"lowest_balance": 3000.0}, kart_borcu=1000.0) == 2000.0


def test_cockpit_123_kart_batik_alacakli_senaryo(db):
    """
    BUG #123 regresyon: alacak forecast'i pozitife taşısa BİLE, büyük kart borcu varken
    güvenli harcama 0 olmalı (uçtan-uca gözlemle yakalanan çelişki).
    """
    from datetime import timedelta
    from app.models import Account, AccountType, PersonalDebt, DebtDirection
    _cash(db, 4276.0)
    db.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                   balance=11976.0, credit_limit=12000.0))
    # Efe alacağı forecast'i pozitife taşır (eskiden güvenli-harcama = 4276 gösteriyordu)
    db.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                        amount=8000.0, is_paid=False, due_date=TODAY + timedelta(days=3)))
    db.commit()
    cockpit = generate_cockpit(1, TODAY, db)
    assert cockpit["guvenli_harcama"] == 0.0     # kart borcu düşülünce güvenli para yok
