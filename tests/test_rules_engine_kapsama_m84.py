"""
M84 (Wave-6) — rules_engine kapsanmayan iş-mantığı dallarını kapatır.

Wave-5 M71 workspace yolunu test etti; bu dosya kalan util/statü/emanet/deprecated dallarını
bitirir (rules_engine %96 → hedef daha yüksek). Saf-fonksiyon + cockpit-tabanlı dallar.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, RecurringIncome, RecurringExpense
from app.rules_engine import (
    get_next_occurrence, calculate_today_target, calculate_carried_forward,
    generate_cockpit, _collect_upcoming_reminders,
)

TODAY = date(2026, 7, 18)


# ============================================================
# Saf fonksiyonlar — util dalları
# ============================================================

def test_get_next_occurrence_bu_ay():
    """day_of_month bugünden ileri → bu ay döner."""
    assert get_next_occurrence(25, TODAY) == date(2026, 7, 25)


def test_get_next_occurrence_sonraki_ay():
    """day_of_month bugünden geçmiş/eşit → sonraki ay (202-209 dalı)."""
    # bugün 18 > 10 → ağustos 10
    assert get_next_occurrence(10, TODAY) == date(2026, 8, 10)


def test_get_next_occurrence_yil_devri():
    """Aralık → sonraki yıl ocak (210-215 dalı)."""
    dec = date(2026, 12, 20)
    assert get_next_occurrence(5, dec) == date(2027, 1, 5)


def test_get_next_occurrence_kisa_ay_klemp():
    """31 gün-of-month + şubat → ayın son gününe klemplenir."""
    jan31 = date(2026, 1, 31)
    # şubat 2026 (28 gün) → 28
    assert get_next_occurrence(31, jan31) == date(2026, 2, 28)


def test_calculate_today_target_deprecated():
    """DEPRECATED (ADR-026) additive today_target = daily_limit + carry (261-267 dalı)."""
    assert calculate_today_target(100.0, 20.0) == 120.0
    assert calculate_today_target(100.0, -30.0) == 70.0


def test_calculate_carried_forward():
    """Devreden = dünün limiti − dün harcanan."""
    assert calculate_carried_forward(100.0, 60.0) == 40.0
    assert calculate_carried_forward(100.0, 130.0) == -30.0


# ============================================================
# Cockpit-tabanlı dallar — statü + emanet
# ============================================================

@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def test_cockpit_likidite_baskisi_statusu(db):
    """
    reel_butce ≥ 0 AMA kart_borcu/nakit > 2 → 'Likidite baskısı yüksek' statüsü (satır 2020).
    Yüksek düzenli gelir reel bütçeyi pozitif tutar; kart borcu nakdin 3 katı.
    """
    u = User(name="murat", email="m@x.com"); db.add(u); db.commit()
    db.add_all([
        Account(user_id=u.id, name="Nakit", account_type=AccountType.cash, balance=1000),
        Account(user_id=u.id, name="Kart", account_type=AccountType.credit_card,
                balance=3000, credit_limit=12000),
        RecurringIncome(user_id=u.id, name="Maaş", amount=15000, day_of_month=28, is_active=True),
    ])
    db.commit()
    c = generate_cockpit(u.id, TODAY, db)
    assert c["kart_borcu"] == 3000.0
    assert c["nakit_kasa"] == 1000.0
    assert "Likidite baskısı" in c["statu"], f"statu: {c['statu']}"


def test_cockpit_emanet_deger(db):
    """is_emanet yatırım hesabı → emanet_kasa'ya yazılır, yatirim_deger'e DEĞİL (satır 1943)."""
    u = User(name="murat", email="m@x.com"); db.add(u); db.commit()
    db.add_all([
        Account(user_id=u.id, name="Nakit", account_type=AccountType.cash, balance=5000),
        Account(user_id=u.id, name="Emanet TLY", account_type=AccountType.investment,
                lot_count=10, current_price=100, is_emanet=True),
        Account(user_id=u.id, name="Yatırım", account_type=AccountType.investment,
                lot_count=5, current_price=200, is_emanet=False),
    ])
    db.commit()
    c = generate_cockpit(u.id, TODAY, db)
    assert c["emanet_kasa"] == 1000.0   # 10 * 100
    assert c["yatirim_deger"] == 1000.0  # 5 * 200


def test_reminder_kart_riski(db):
    """Neredeyse dolu kartta vadesi yaklaşan düzenli gider → card_risk=True (satır 693-702)."""
    u = User(name="murat", email="m@x.com"); db.add(u); db.commit()
    kart = Account(user_id=u.id, name="Kart", account_type=AccountType.credit_card,
                   balance=11500, credit_limit=12000)
    db.add(kart); db.commit()
    # 800 TL gider + 11500 bakiye = 12300 > 12000 limit → card_risk
    db.add(RecurringExpense(user_id=u.id, name="Fatura", amount=800, account_id=kart.id,
                            day_of_month=20, is_active=True))
    db.commit()
    accounts = db.query(Account).filter(Account.user_id == u.id).all()
    reminders = _collect_upcoming_reminders(u.id, TODAY, db, accounts, kart_borcu=11500)
    fatura = next((r for r in reminders if r["name"] == "Fatura"), None)
    assert fatura is not None, f"reminder bulunamadı: {reminders}"
    assert fatura["card_risk"] is True
