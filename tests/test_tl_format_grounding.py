"""
BUG #122 — alert/mesaj tutarları Türkçe para formatı (virgül ondalık) + grounding tutarlılığı.
Eskiden '{:,.2f}' NOKTA ondalık ("74.99 TL") üretiyordu → koç echo edince grounding _TL_NUM_RE
noktayı binlik sanıp yanlış tutar okuyordu (yanlış-pozitif). _tl() bunu düzeltir.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, PersonalDebt, DebtDirection
from app.rules_engine import _tl, generate_cockpit
from app.grounding import check_grounding


def test_tl_turkce_format():
    assert _tl(1234.56) == "1.234,56"
    assert _tl(74.99) == "74,99"
    assert _tl(1000000) == "1.000.000,00"
    assert _tl(-2500.5) == "-2.500,50"


def test_tl_grounding_ile_uyumlu():
    """_tl çıktısı grounding'in Türkçe formatı ile birebir eşleşir (echo edilince izlenir)."""
    # _tl(74.99)="74,99"; grounding bunu 74.99 olarak parse etmeli
    cockpit = {"_coach_extra_numbers": [74.99]}
    g = check_grounding(f"Abonelik {_tl(74.99)} TL oldu.", cockpit)
    assert g["ok"] is True


def test_nokta_format_grounding_kaciriyordu():
    """
    Regresyon kanıtı: NOKTA ondalık hallüsinasyon tutarı grounding'i ATLATIYORDU.
    "1500.50 TL" → _TL_NUM_RE ondalık kısmı "50 TL" okur (<100 → atlanır) → tutar hiç
    denetlenmez (yanlış-negatif). Türkçe format ("1.500,50") ise 1500.50 olarak yakalanır.
    """
    bos_cockpit = {"_coach_extra_numbers": []}   # hiçbir tutar meşru değil
    # Türkçe format: hayali tutar YAKALANIR
    g_tr = check_grounding("Hayali 1.500,50 TL borç var.", bos_cockpit)
    assert g_tr["ok"] is False and 1500.50 in g_tr["unverified"]
    # Nokta format (eski): grounding kaçırıyordu (yanlış-negatif)
    g_dot = check_grounding("Hayali 1500.50 TL borç var.", bos_cockpit)
    assert g_dot["ok"] is True   # eski format hallüsinasyonu izlemiyordu → #122'nin değeri


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


def test_overdue_alert_turkce_formatli(db):
    """Gecikmiş borç alert mesajı artık Türkçe formatlı tutar içerir."""
    today = date(2026, 5, 20)
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=3000.0))
    db.add(PersonalDebt(user_id=1, counterparty="Kirveci", direction=DebtDirection.payable,
                        amount=2500.0, is_paid=False, due_date=today - timedelta(days=4)))
    db.commit()
    cockpit = generate_cockpit(1, today, db)
    overdue = next(a for a in cockpit["alerts"] if a["baslik"].startswith("Gecikmiş borç"))
    assert "2.500,00 TL" in overdue["mesaj"]      # Türkçe format
