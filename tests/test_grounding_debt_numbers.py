"""
Grounding entegrasyon kilidi — koç YENİ borç/alacak metriklerinin (FEAT-014/015/027)
TL tutarlarını cevabında yazınca grounding onları DOĞRULANMIŞ saymalı. Aksi halde meşru
deterministik tutarlar "izlenemeyen" sanılıp confidence yanlışlıkla düşerdi (eval'de
grounding-analiz failure mode'u tam buydu — bu regresyonu kilitliyoruz).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Account, AccountType, PersonalDebt, DebtDirection,
)
from app.coach import _build_context_message
from app.grounding import check_grounding


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    today = date.today()
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    s.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                  balance=11976.0, credit_limit=12000.0, interest_rate=4.25))
    s.add(Account(user_id=1, name="Kredi1", account_type=AccountType.loan,
                  balance=30000.0, interest_rate=2.9, monthly_payment=2500,
                  remaining_installments=12))
    s.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                       amount=9000.0, due_date=today - timedelta(days=95), is_paid=False))
    s.commit()
    yield s
    s.close()


def _tl(n):
    """Türkçe para formatı (grounding _TL_NUM_RE'nin beklediği biçim)."""
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def test_yeni_borç_metrik_tutarları_grounded(db):
    context, cockpit = _build_context_message(db, 1)
    trap = cockpit["asgari_tuzagi"]["kartlar"][0]
    aging = cockpit["alacak_yaslanma"]
    kons = cockpit["konsolidasyon"]

    # koç bu meşru deterministik tutarları cevabında yazsa grounding DOĞRULAMALI
    reply = (
        f"Kart asgari ödemeyle {trap['ay']} ayda kapanır, {_tl(trap['toplam_faiz'])} TL faiz. "
        f"Gecikmiş alacağın {_tl(aging['toplam_gecikmis'])} TL. "
        f"Toplam borç {_tl(kons['toplam_bakiye'])} TL."
    )
    g = check_grounding(reply, cockpit)
    assert g["ok"] is True, f"yeni borç metrik tutarları grounding'de izlenemedi: {g['unverified']}"
    assert g["checked"] >= 3


def test_uydurulan_tutar_yakalanir(db):
    """Kontrol: cockpit'te OLMAYAN bir tutar hâlâ yakalanmalı (grounding körelmemiş)."""
    _, cockpit = _build_context_message(db, 1)
    g = check_grounding("Beklenmedik 88.888 TL borç var.", cockpit)
    assert g["ok"] is False
    assert 88888.0 in g["unverified"]


def test_utilization_tutarlari_grounded(db):
    """
    FEAT-016: koç kart utilization TL tutarlarını (toplam borç/limit, %30 sağlıklı borç hedefi)
    yazınca grounding DOĞRULAMALI — bu sayılar _build_context_message'da _coach_extra_numbers'a
    kaydedilir (kart %99.8 → kritik bant → blok aktif). Aksi halde meşru hedef "izlenemeyen"
    sanılıp confidence düşerdi.
    """
    context, cockpit = _build_context_message(db, 1)
    ku = cockpit["kart_kullanim"]
    assert ku is not None and ku["band"] == "kritik"
    reply = (
        f"Kart kullanımın %{ku['oran']}. Toplam borç {_tl(ku['toplam_borc'])} TL, "
        f"limit {_tl(ku['toplam_limit'])} TL. %30'a inmek için borç "
        f"{_tl(ku['saglikli_borc_hedefi'])} TL seviyesine düşmeli."
    )
    g = check_grounding(reply, cockpit)
    assert g["ok"] is True, f"utilization tutarları grounding'de izlenemedi: {g['unverified']}"
