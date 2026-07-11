"""
FEAT-015 — kart asgari-ödeme tuzağı. Kart SADECE asgari ödemeyle kaç ay + toplam faiz.
calculate_min_payment_trap (saf sim) + cockpit entegrasyonu + alert + koç context.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType
from app.debt_strategy import DebtItem, calculate_min_payment_trap
from app.rules_engine import generate_cockpit, _min_payment_trap_alerts

TODAY = date(2026, 7, 12)


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


def _card(balance, rate=4.25):
    return DebtItem(account_id=1, name="Ziraat", account_type="credit_card",
                    balance=balance, interest_rate_monthly=rate, min_payment=0)


def _loan(balance, rate=2.0):
    return DebtItem(account_id=2, name="Kredi", account_type="loan",
                    balance=balance, interest_rate_monthly=rate, min_payment=500)


# ---- calculate_min_payment_trap (saf) --------------------------------------

def test_kart_yoksa_none(db):
    assert calculate_min_payment_trap([], today=TODAY) is None
    assert calculate_min_payment_trap([_loan(10000)], today=TODAY) is None  # sadece kredi → None


def test_kart_asgari_tuzagi_ay_faiz(db):
    t = calculate_min_payment_trap([_card(11976.0)], today=TODAY)
    assert t is not None
    k = t["kartlar"][0]
    assert k["ad"] == "Ziraat"
    assert k["ay"] == 22                      # %25 azalan asgari + %4.25 faiz
    assert 2200 < k["toplam_faiz"] < 2400     # ~2318 TL faiz
    assert k["asla_bitmez"] is False
    assert k["payoff_tarih"] == "2028-05-12"
    assert t["toplam_faiz"] == k["toplam_faiz"]
    assert t["en_yuksek_faiz"] == k


def test_kredi_haric_sadece_kart(db):
    t = calculate_min_payment_trap([_card(5000.0), _loan(20000.0)], today=TODAY)
    assert len(t["kartlar"]) == 1             # kredi listeye girmez
    assert t["kartlar"][0]["ad"] == "Ziraat"


def test_asla_bitmez_asgari_faizden_dusuk(db):
    # rate %40/ay: asgari %25 faiz-SONRASI bakiyeden alınır → eşik %33.3; üstünde asgari
    # ödeme faizi karşılamaz → borç büyür → asla kapanmaz (RULE-011: payoff None)
    t = calculate_min_payment_trap([_card(11976.0, rate=40.0)], today=TODAY)
    k = t["kartlar"][0]
    assert k["asla_bitmez"] is True
    assert k["payoff_tarih"] is None


def test_coklu_kart_faize_gore_sirali(db):
    c1 = DebtItem(account_id=1, name="Az", account_type="credit_card",
                  balance=2000.0, interest_rate_monthly=4.25, min_payment=0)
    c2 = DebtItem(account_id=2, name="Cok", account_type="credit_card",
                  balance=15000.0, interest_rate_monthly=4.25, min_payment=0)
    t = calculate_min_payment_trap([c1, c2], today=TODAY)
    assert t["kartlar"][0]["ad"] == "Cok"     # en çok sızdıran önce
    assert t["en_yuksek_faiz"]["ad"] == "Cok"


# ---- _min_payment_trap_alerts ----------------------------------------------

def test_alert_uzun_kuyruk_uyari(db):
    t = calculate_min_payment_trap([_card(11976.0)], today=TODAY)  # 22 ay
    alerts = _min_payment_trap_alerts(t)
    assert len(alerts) == 1
    assert alerts[0]["seviye"] == "uyari"
    assert "asgari" in alerts[0]["baslik"].lower()
    assert "2.317,93" in alerts[0]["mesaj"] or "2.318" in alerts[0]["mesaj"]  # Türkçe format


def test_alert_asla_bitmez_kritik(db):
    t = calculate_min_payment_trap([_card(11976.0, rate=40.0)], today=TODAY)
    alerts = _min_payment_trap_alerts(t)
    assert alerts[0]["seviye"] == "kritik"
    assert "sarmal" in alerts[0]["mesaj"].lower() or "ASLA" in alerts[0]["mesaj"]


def test_alert_kisa_kuyruk_uyari_yok(db):
    # küçük bakiye → asgari 50 TL floor → hızlı kapanır (<12 ay) → uyarı yok
    t = calculate_min_payment_trap([_card(300.0)], today=TODAY)
    assert _min_payment_trap_alerts(t) == []


def test_alert_bos_none(db):
    assert _min_payment_trap_alerts(None) == []
    assert _min_payment_trap_alerts({"kartlar": []}) == []


# ---- cockpit + koç entegrasyonu --------------------------------------------

def test_cockpit_asgari_tuzagi_alani(db):
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    db.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                   balance=11976.0, credit_limit=12000.0, interest_rate=4.25))
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    assert c["asgari_tuzagi"] is not None
    assert c["asgari_tuzagi"]["kartlar"][0]["ad"] == "Ziraat"
    trap = [a for a in c["alerts"] if "asgari" in a["baslik"].lower()]
    assert len(trap) == 1


def test_cockpit_kart_yoksa_none(db):
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    assert c["asgari_tuzagi"] is None


def test_koc_contextine_duser(db):
    from app.coach import _build_context_message
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    db.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                   balance=11976.0, credit_limit=12000.0, interest_rate=4.25))
    db.commit()
    context, cockpit = _build_context_message(db, 1)
    assert "ASGARİ ÖDEME TUZAĞI" in context
    # grounding: tuzak faiz tutarı _coach_extra_numbers'a tanıtılmış olmalı
    assert any(abs(n - cockpit["asgari_tuzagi"]["toplam_faiz"]) < 0.01
               for n in cockpit.get("_coach_extra_numbers", []))
