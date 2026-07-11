"""
Koç bağlamı (context) veri-kablolaması — deterministik sinyallerin LLM'e ULAŞTIĞINI kilitler.
"Rules Engine karar verir, LLM açıklar" için LLM'in sinyali GÖRMESİ ön koşul: gecikmiş borç
alert'i (#120) ve yaklaşan alacak tahsilatı (#119) _build_context_message çıktısında olmalı.
(LLM'in bunları nasıl kullandığı ayrı; burada yalnızca verinin bağlama düştüğünü doğruluyoruz.)
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, PersonalDebt, DebtDirection
from app.coach import _build_context_message


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=3000.0))
    s.commit()
    yield s
    s.close()


def test_gecikmis_borc_baglama_duser(db):
    """#120: vadesi geçmiş ödenmemiş borç → context'te gecikme uyarısı görünür."""
    today = date.today()
    db.add(PersonalDebt(user_id=1, counterparty="Kirveci", direction=DebtDirection.payable,
                        amount=2500.0, is_paid=False, due_date=today - timedelta(days=4)))
    db.commit()

    context, cockpit = _build_context_message(db, 1)
    assert "Gecikmiş borç: Kirveci" in context
    assert any(a["baslik"].startswith("Gecikmiş borç") for a in cockpit["alerts"])


def test_yaklasan_alacak_tahsilati_baglama_duser(db):
    """#119: 0-7 gün içinde vadesi gelen alacak → context YAKLAŞAN VADELER'de görünür."""
    today = date.today()
    db.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                        amount=1800.0, is_paid=False, due_date=today + timedelta(days=3)))
    db.commit()

    context, cockpit = _build_context_message(db, 1)
    assert "Efe alacağı" in context
    assert any(r["type"] == "receivable" for r in cockpit["upcoming_reminders"])
