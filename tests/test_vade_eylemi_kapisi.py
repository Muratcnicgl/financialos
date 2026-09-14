"""
UX-013 (BUG #477): yaklaşan vade satırı eyleme dönüşür — kaynak kimliği sözleşmesi.

Ölçüm (14 Eyl 2026): `upcoming_reminders` kalemleri ad/tutar/gün taşıyordu, kayıt kimliği
taşımıyordu; arayüz satırdan "Ödedim/Geldi" yapamazdı (hangi kaydı kapatacağını bilemezdi).
Bu kapı beş kalem tipinin de `kaynak_id` taşıdığını ve kimliğin DOĞRU kayda ait olduğunu
kilitler; arayüz tarafı `frontend/src/vade-eylemi.test.jsx`.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Account, AccountType, Base, DebtDirection, PersonalDebt, RecurringExpense, RecurringIncome, User,
)
from app.rules_engine import _collect_upcoming_reminders


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="test"))
    s.commit()
    yield s
    s.close()


def _gun(today: date, ileri: int) -> int:
    """Bugünden `ileri` gün sonraki ayın-günü (0–7 penceresinde kalacak şekilde)."""
    return (today + timedelta(days=ileri)).day


def test_bes_kalem_tipi_de_kaynak_id_tasir(db):
    today = date(2026, 9, 10)   # ay ortası: gün aritmetiği ay sınırına takılmaz
    nakit = Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=5000)
    kart = Account(user_id=1, name="Kart", account_type=AccountType.credit_card, balance=1200,
                   credit_limit=10000, payment_day=_gun(today, 3), statement_balance=900)
    db.add_all([nakit, kart])
    db.flush()
    gelir = RecurringIncome(user_id=1, name="Maaş", amount=30000, day_of_month=_gun(today, 2), is_active=True)
    gider = RecurringExpense(user_id=1, name="Kira", amount=12000, day_of_month=_gun(today, 4),
                             is_active=True, account_id=nakit.id)
    borc = PersonalDebt(user_id=1, counterparty="Ali", direction=DebtDirection.payable, amount=500,
                        is_paid=False, due_date=today + timedelta(days=1))
    alacak = PersonalDebt(user_id=1, counterparty="Veli", direction=DebtDirection.receivable, amount=700,
                          is_paid=False, due_date=today + timedelta(days=5))
    db.add_all([gelir, gider, borc, alacak])
    db.commit()

    hatirlatmalar = _collect_upcoming_reminders(1, today, db, [nakit, kart], 1200)
    kimlik = {r["type"]: r["kaynak_id"] for r in hatirlatmalar}
    assert set(kimlik) == {"income", "expense", "debt", "receivable", "card_payment"}, kimlik
    assert kimlik["income"] == gelir.id
    assert kimlik["expense"] == gider.id
    assert kimlik["debt"] == borc.id
    assert kimlik["receivable"] == alacak.id
    assert kimlik["card_payment"] == kart.id
    # Kimlik "bir sayı" değil, doğru kayıt: borç ile alacak farklı kayıtlar.
    assert kimlik["debt"] != kimlik["receivable"]


def test_arayuz_eylem_haritasi_kaynaktan():
    """Kokpit satırı borç/alacak/kart için eylem taşır; düzenli kayıt bilerek taşımaz."""
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent / "frontend" / "src"
    ck = (kok / "panels" / "Cockpit.jsx").read_text(encoding="utf-8")
    assert "r.type === 'debt' ? { etiket: 'Ödedim'" in ck
    assert "r.type === 'receivable' ? { etiket: 'Geldi'" in ck
    assert "r.type === 'card_payment' ? { etiket: 'Koça sor'" in ck
    assert "r.kaynak_id == null ? null" in ck, "kimliksiz kalem eylem taşımamalı"
    # tek kaynak: hem panel hem kokpit aynı yardımcıdan kapatır
    inc = (kok / "panels" / "IncomeDebt.jsx").read_text(encoding="utf-8")
    assert "borcuKapat(" in inc and "borcuKapat(" in ck
    assert "debtsApi.update(debt.id, { is_paid: true" not in inc, "IncomeDebt kendi kopyasını taşıyor"
