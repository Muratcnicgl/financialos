"""
BUG #121 (DEVRİMSEL) — ileriye dönük NAKİT KRİZİ öngörüsü alert'i.
_detect_cashflow_crunch + generate_cockpit entegrasyonu: sistem artık gelecekteki
insolvency'yi kriz OLMADAN önce uyarır. Deterministik izole DB.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, PersonalDebt, DebtDirection
from app.rules_engine import _detect_cashflow_crunch, generate_cockpit
from app.grounding import check_grounding


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


def _payable(db, amount, due_in_days, today):
    d = PersonalDebt(user_id=1, counterparty="Banka", direction=DebtDirection.payable,
                     amount=amount, is_paid=False, due_date=today + timedelta(days=due_in_days))
    db.add(d); db.commit(); db.refresh(d)
    return d


def test_121_projekte_kriz_alert_uretir(db):
    """Nakit 1000, 10 gün sonra 3000 borç → projeksiyon −2000 → nakit krizi alert'i."""
    today = date(2026, 5, 1)
    _cash(db, 1000.0)
    _payable(db, 3000.0, 10, today)

    alert = _detect_cashflow_crunch(1, today, db)
    assert alert is not None
    assert alert["seviye"] == "kritik"
    assert alert["baslik"] == "Nakit krizi öngörüsü"
    assert "ÖNLENEBİLİR" in alert["mesaj"]
    assert alert["tutar"] == 2000.0        # abs(en düşük bakiye)


def test_121_solvent_senaryoda_alert_yok(db):
    """Nakit 5000, 10 gün sonra 1000 borç → bakiye 4000, kriz yok → None."""
    today = date(2026, 5, 1)
    _cash(db, 5000.0)
    _payable(db, 1000.0, 10, today)
    assert _detect_cashflow_crunch(1, today, db) is None


def test_121_bos_veri_alert_yok(db):
    """Hiç akış yoksa kriz yok."""
    today = date(2026, 5, 1)
    _cash(db, 500.0)
    assert _detect_cashflow_crunch(1, today, db) is None


def test_121_generate_cockpit_alerts_e_dusuyor(db):
    """Uçtan uca: projekte kriz generate_cockpit alerts'ine kritik olarak düşer."""
    today = date(2026, 5, 1)
    _cash(db, 1000.0)
    _payable(db, 3000.0, 10, today)

    cockpit = generate_cockpit(1, today, db)
    crunch = [a for a in cockpit["alerts"] if a.get("baslik") == "Nakit krizi öngörüsü"]
    assert len(crunch) == 1
    assert crunch[0]["seviye"] == "kritik"


def test_121_kriz_tutari_grounding_dogrulanir(db):
    """Koç projekte kriz tutarını yazınca grounding onu DOĞRULANMIŞ saymalı (numerik tutar)."""
    today = date(2026, 5, 1)
    _cash(db, 1000.0)
    _payable(db, 3000.0, 10, today)

    cockpit = generate_cockpit(1, today, db)
    reply = "Dikkat: 2.000 TL nakit açığı öngörülüyor, tedbir al."
    g = check_grounding(reply, cockpit)
    assert g["ok"] is True, f"kriz tutarı izlenemedi: {g['unverified']}"


def test_121_gecikmis_borc_krizden_once_gelir(db):
    """Sıralama: hem gecikmiş borç (present) hem projekte kriz (future) varsa,
    gecikmiş (anlık) önce gelir; kriz onu takip eder."""
    today = date(2026, 5, 1)
    _cash(db, 1000.0)
    # gecikmiş borç (present)
    db.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.payable,
                        amount=500.0, is_paid=False, due_date=today - timedelta(days=3)))
    # gelecekteki kriz kaynağı
    _payable(db, 3000.0, 10, today)
    db.commit()

    cockpit = generate_cockpit(1, today, db)
    basliklar = [a["baslik"] for a in cockpit["alerts"]]
    i_gecikme = next(i for i, b in enumerate(basliklar) if b.startswith("Gecikmiş"))
    i_kriz = basliklar.index("Nakit krizi öngörüsü")
    assert i_gecikme < i_kriz
