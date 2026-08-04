"""
FEAT-031 — "Güvenli borç ödemesi" (safe debt payment).

guvenli_borc_odemesi = max(0, lowest_forecast_balance - buffer). Bugün X ödemek tüm gelecek
projekte bakiyeleri X düşürür → güvenle ödenebilir tutar en düşük projekte bakiyeye eşittir.
`guvenli_harcama`'dan farkı: borç ödemesi o borcu ORTADAN kaldırır → kart_borcu DÜŞÜLMEZ.

Kök: koç "karta ne kadar öderim?" sorusunda `guvenli_harcama`'yı (harcama bütçesi) yanlışlıkla
ödeme tutarı sanıyordu (uydurma, ADR-001 ihlali). Bu metrik doğru sayıyı + senaryo menüsünü verir.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, PersonalDebt, DebtDirection
from app.rules_engine import (
    _calculate_safe_debt_payment,
    build_safe_debt_payment_scenarios,
    generate_cockpit,
)
from app import settings

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
    assert _calculate_safe_debt_payment(None) == 0.0


def test_pure_lowest_pozitif_tampon_yok():
    assert _calculate_safe_debt_payment({"lowest_balance": 8500.0}) == 8500.0


def test_pure_tampon_dususu():
    assert _calculate_safe_debt_payment({"lowest_balance": 8500.0}, buffer=2000.0) == 6500.0


def test_pure_tampon_lowesttan_buyuk_sifir():
    assert _calculate_safe_debt_payment({"lowest_balance": 4573.52}, buffer=5000.0) == 0.0


def test_pure_kart_borcu_DUSULMEZ():
    """guvenli_harcama'nın aksine: borç ödemesi o borcu kaldırır → kart_borcu düşülmez.
    Aynı lowest ile bu fonksiyon guvenli_harcama'dan (kart düşülmüş) BÜYÜK olmalı."""
    from app.rules_engine import _calculate_safe_to_spend
    summary = {"lowest_balance": 5000.0}
    assert _calculate_safe_debt_payment(summary) == 5000.0
    assert _calculate_safe_to_spend(summary, kart_borcu=3000.0) == 2000.0  # harcama kartı düşer


# ---- senaryo menüsü --------------------------------------------------------

def test_senaryolar_summary_yoksa_uygun_degil():
    res = build_safe_debt_payment_scenarios(None, 2000.0, kredi_borcu=50000.0)
    assert res["uygun"] is False
    assert res["sebep"] == "ongoru_yok"


def test_senaryolar_borc_yoksa_uygun_degil():
    """Canlı-test dersi: kart+kredi=0 → ödenecek borç yok, koç öneri sunmasın."""
    res = build_safe_debt_payment_scenarios({"lowest_balance": 8500.0}, 2000.0, kart_borcu=0.0, kredi_borcu=0.0)
    assert res["uygun"] is False
    assert res["sebep"] == "borc_yok"
    assert res["kart_borcu"] == 0.0


def test_senaryolar_yapisi_ve_varsayilan_isareti():
    # kredi 50k → kapasite (8500) borçtan küçük, kapama YOK
    res = build_safe_debt_payment_scenarios(
        {"lowest_balance": 8500.0, "lowest_date": "2026-05-20"}, 2000.0, kredi_borcu=50000.0)
    assert res["uygun"] is True
    assert res["en_dusuk_nakit"] == 8500.0
    assert res["en_dusuk_tarih"] == "2026-05-20"
    assert res["varsayilan_tampon"] == 2000.0
    assert res["onerilen_odeme"] == 6500.0
    assert res["kredi_borcu"] == 50000.0
    assert res["toplam_borc"] == 50000.0
    # tamponlar {0, 2000, 5000}, artan sırada
    tamponlar = [s["tampon"] for s in res["senaryolar"]]
    assert tamponlar == [0.0, 2000.0, 5000.0]
    odemeler = {s["tampon"]: s["odenebilir"] for s in res["senaryolar"]}
    assert odemeler == {0.0: 8500.0, 2000.0: 6500.0, 5000.0: 3500.0}
    # yalnız varsayılan (2000) işaretli
    isaretli = [s["tampon"] for s in res["senaryolar"] if s["varsayilan"]]
    assert isaretli == [2000.0]


def test_odenebilir_mevcut_borcla_sinirli():
    """Kapasite 8500 ama toplam borç 500 → en fazla 500 ödenebilir (borçtan fazlası ödenemez)."""
    res = build_safe_debt_payment_scenarios({"lowest_balance": 8500.0}, 2000.0, kart_borcu=500.0)
    odemeler = {s["tampon"]: s["odenebilir"] for s in res["senaryolar"]}
    assert odemeler == {0.0: 500.0, 2000.0: 500.0, 5000.0: 500.0}
    assert res["onerilen_odeme"] == 500.0


def test_senaryolar_ozel_varsayilan_tampon_setine_dahil():
    """SAFE_DEBT_BUFFER=3000 gibi özel değer senaryolara girsin (birden fazla seçenek)."""
    res = build_safe_debt_payment_scenarios(
        {"lowest_balance": 10000.0, "lowest_date": "2026-05-10"}, 3000.0, kredi_borcu=50000.0)
    tamponlar = [s["tampon"] for s in res["senaryolar"]]
    assert tamponlar == [0.0, 3000.0, 5000.0]
    assert res["onerilen_odeme"] == 7000.0


# ---- settings (ayarlanabilir tampon) --------------------------------------

def test_settings_varsayilan_2000(monkeypatch):
    monkeypatch.delenv("SAFE_DEBT_BUFFER", raising=False)
    assert settings.safe_debt_buffer() == 2000.0


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("SAFE_DEBT_BUFFER", "3500")
    assert settings.safe_debt_buffer() == 3500.0


def test_settings_gecersiz_deger_varsayilana_doner(monkeypatch):
    monkeypatch.setenv("SAFE_DEBT_BUFFER", "abc")
    assert settings.safe_debt_buffer() == 2000.0


def test_settings_negatif_varsayilana_doner(monkeypatch):
    monkeypatch.setenv("SAFE_DEBT_BUFFER", "-500")
    assert settings.safe_debt_buffer() == 2000.0


# ---- generate_cockpit entegrasyonu ----------------------------------------

def _loan(db, balance):
    a = Account(user_id=1, name="Kredi", account_type=AccountType.loan, balance=balance)
    db.add(a); db.commit(); db.refresh(a)
    return a


def test_cockpit_guvenli_borc_odemesi_alani_var(db):
    _cash(db, 5000.0)
    _loan(db, 30000.0)  # ödenecek borç olmalı ki senaryolar üretilsin
    cockpit = generate_cockpit(1, TODAY, db)
    assert "guvenli_borc_odemesi" in cockpit
    gbo = cockpit["guvenli_borc_odemesi"]
    assert gbo["uygun"] is True
    assert len(gbo["senaryolar"]) == 3


def test_cockpit_borc_yoksa_uygun_degil(db):
    """Kart+kredi=0 (canlı-test senaryosu) → uygun=False, koç 0-borca ödeme önermez."""
    _cash(db, 5000.0)
    cockpit = generate_cockpit(1, TODAY, db)
    gbo = cockpit["guvenli_borc_odemesi"]
    assert gbo["uygun"] is False
    assert gbo["sebep"] == "borc_yok"


def test_cockpit_lumpy_borc_odeme_tavani_kisitlar(db):
    """Nakit 5000, 20 gün sonra 4000 payable → en düşük projekte 1000 → 0 tamponda 1000
    ödenebilir. Kredi borcu 30k var (kapama tavanı 1000'in üstünde, kısıtlamaz)."""
    _cash(db, 5000.0)
    _loan(db, 30000.0)
    _payable(db, 4000.0, 20)
    cockpit = generate_cockpit(1, TODAY, db)
    gbo = cockpit["guvenli_borc_odemesi"]
    sifir_tampon = next(s for s in gbo["senaryolar"] if s["tampon"] == 0.0)
    assert sifir_tampon["odenebilir"] == 1000.0
