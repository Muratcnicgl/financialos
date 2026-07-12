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


# ---- kenar-durum portföyleri: koç bağlamı ASLA çökmemeli (core feature koruması) ----

def _fresh():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="m"))
    s.commit()
    return s


def _setup_bos(s):
    pass  # hiç hesap yok


def _setup_yalniz_borc(s):
    s.add(Account(user_id=1, name="K", account_type=AccountType.credit_card,
                  balance=50000, credit_limit=50000))  # kart tam dolu, nakit yok


def _setup_sifir_limit_kart(s):
    s.add(Account(user_id=1, name="K", account_type=AccountType.credit_card,
                  balance=5000, credit_limit=0))  # limit 0 → utilization None (bölme yok)


def _setup_devasa(s):
    s.add(Account(user_id=1, name="N", account_type=AccountType.cash, balance=1e12))
    s.add(Account(user_id=1, name="K", account_type=AccountType.credit_card,
                  balance=9e11, credit_limit=1e12))


@pytest.mark.parametrize("setup", [
    _setup_bos, _setup_yalniz_borc, _setup_sifir_limit_kart, _setup_devasa,
], ids=["bos", "yalniz_borc", "sifir_limit_kart", "devasa"])
def test_kenar_portfoy_baglam_cokmez(setup):
    """
    Koç THE çekirdek etkileşim — _build_context_message olağandışı-ama-geçerli portföyde
    (boş, yalnız-borç, sıfır-limit kart, devasa sayılar) çökerse koç tamamen kırılır.
    Çökme YOK + bağlam boş değil.
    """
    s = _fresh()
    try:
        setup(s)
        s.commit()
        context, cockpit = _build_context_message(s, 1)
        assert isinstance(context, str) and len(context) > 0
        assert isinstance(cockpit, dict)
    finally:
        s.close()


# ---- FEAT-017 kilometre taşı: taze band geçişi koç bağlamında kutlanır ----

def test_yeni_milestone_koc_baglaminda_kutlanir():
    """Taze band geçişinde (%25) koç context'inde 'KİLOMETRE TAŞI' kutlama bloğu görünmeli."""
    from datetime import date, timedelta
    from app.models import NetWorthSnapshot, RecurringIncome
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    today = date(2026, 7, 12)
    try:
        s.add(User(id=1, name="murat"))
        # bugünkü borç: kredi 74k (guncel). baseline 100k, dünkü 80k → band 10→25 taze geçiş.
        s.add(Account(user_id=1, name="Kredi", account_type=AccountType.loan, balance=74000,
                      monthly_payment=3000, remaining_installments=25,
                      next_payment_date=today + timedelta(days=5)))
        s.add(NetWorthSnapshot(user_id=1, snapshot_date=today - timedelta(days=30), net_worth_seen=0,
                               net_worth_full=0, cash=0, card_debt=0, loan_debt=100000,
                               investment_value=0, receivables=0))
        s.add(NetWorthSnapshot(user_id=1, snapshot_date=today - timedelta(days=1), net_worth_seen=0,
                               net_worth_full=0, cash=0, card_debt=0, loan_debt=80000,
                               investment_value=0, receivables=0))
        s.commit()
        context, cockpit = _build_context_message(s, 1)
        assert cockpit["borc_ilerleme"]["yeni_milestone"] == 25
        assert "KİLOMETRE TAŞI" in context
    finally:
        s.close()
