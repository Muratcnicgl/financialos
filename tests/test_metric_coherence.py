"""
Metrik TUTARLILIK invariant'ları — ileriye-dönük sinyaller (daily_limit / guvenli_harcama /
runway / crunch) birbiriyle ÇELİŞMEMELİ. #123 (safe-to-spend kart-farkındalığı) ve #124
(runway kredi-farkındalığı) uçtan-uca gözlemle yakalanan çelişkilerdi; bu testler emergent
tutarlılığı kilitler → gelecekte bir değişiklik çelişkiyi sessizce geri getiremez.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Account, AccountType, Transaction, TransactionType,
    PersonalDebt, DebtDirection, RecurringIncome,
)
from app.rules_engine import generate_cockpit

TODAY = date(2026, 5, 15)


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


def test_kart_batikken_guvenli_harcama_sifir_ve_reel_butce_negatif(db):
    """
    #123 invariant: kart nakdi aşıyorsa (hayatta kalma) reel_butce < 0 VE guvenli_harcama == 0.
    Bir alacak forecast'i pozitife taşısa bile ikisi AYNI yönde olmalı (çelişki yok).
    """
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    db.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                   balance=11976.0, credit_limit=12000.0))
    db.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                        amount=8000.0, is_paid=False, due_date=TODAY + timedelta(days=3)))
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    assert c["reel_butce"] < 0
    assert c["guvenli_harcama"] == 0.0, "kart batıkken güvenli harcama 0 olmalı (#123)"


def test_crunch_varsa_runway_kisa(db):
    """
    #124 invariant: nakit-krizi öngörüsü (crunch) varsa runway UZUN olamaz — ikisi de aynı
    kredilerin baskısını ölçer. Çelişki (runway 300 + crunch) olmamalı.
    """
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=6000.0))
    db.add(Account(user_id=1, name="K1", account_type=AccountType.loan, balance=30000.0,
                   monthly_payment=5000.0, remaining_installments=6, next_payment_date=date(2026, 5, 20)))
    db.add(Account(user_id=1, name="K2", account_type=AccountType.loan, balance=20000.0,
                   monthly_payment=4000.0, remaining_installments=5, next_payment_date=date(2026, 5, 25)))
    db.add(RecurringIncome(user_id=1, name="KYK", amount=4000.0, day_of_month=8, is_active=True))
    for i in range(6):
        db.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=100.0,
                           category="market", transaction_date=TODAY - timedelta(days=i * 2)))
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    crunch = [a for a in c["alerts"] if "kriz" in a["baslik"].lower()]
    assert crunch, "bu senaryoda nakit krizi öngörüsü olmalı"
    assert c["nakit_runway_gun"] is not None and c["nakit_runway_gun"] < 60, \
        f"crunch varken runway kısa olmalı (kredi-farkında), {c['nakit_runway_gun']} bulundu"


def test_utilization_saglik_skoruyla_tutarli(db):
    """
    FEAT-016 invariant: kart_kullanim.oran ile sağlık skoru 'Kart sağlığı' bileşeni AYNI
    tanımdan türer (borç/limit) — birbirini yalanlayamaz. #124-sınıfı çelişki koruması:
    kart_sagligi_puan == round(100 - min(oran, 100)). Ayrıca oran = borç/limit*100.
    """
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    db.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                   balance=11976.0, credit_limit=12000.0))  # %99.8
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    ku = c["kart_kullanim"]
    assert ku is not None and ku["band"] == "kritik"
    assert ku["oran"] == 99.8
    # sağlık skoru bileşeni aynı orandan türemeli
    kart_bilesen = next(b for b in c["saglik_skoru"]["bilesenler"] if b["ad"] == "Kart sağlığı")
    beklenen = round(100 - min(ku["oran"], 100))
    assert abs(kart_bilesen["puan"] - beklenen) <= 1, \
        f"utilization ({ku['oran']}) ile sağlık kart-bileşeni ({kart_bilesen['puan']}) çelişiyor"


def test_alert_siralamasi_kritik_once(db):
    """#125: karışık seviyeli senaryoda TÜM kritik kalemler TÜM uyarılardan önce gelir."""
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    db.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                   balance=11976.0, credit_limit=12000.0))   # kart %99.8 → kritik
    db.add(PersonalDebt(user_id=1, counterparty="Kirveci", direction=DebtDirection.payable,
                        amount=1500.0, is_paid=False, due_date=TODAY - timedelta(days=4)))  # gecikmiş → kritik
    # kategori aşım (uyarı) için geçen ay + bu ay hızlı market
    db.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=1000.0,
                       category="market", transaction_date=date(2026, 4, 10)))
    db.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=900.0,
                       category="market", transaction_date=TODAY - timedelta(days=3)))
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    seviyeler = [a["seviye"] for a in c["alerts"]]
    if "kritik" in seviyeler and "uyari" in seviyeler:
        son_kritik = max(i for i, s in enumerate(seviyeler) if s == "kritik")
        ilk_uyari = min(i for i, s in enumerate(seviyeler) if s == "uyari")
        assert son_kritik < ilk_uyari, f"kritik uyarıdan önce olmalı: {seviyeler}"


def test_alert_yorgunlugu_uyari_capi(db):
    """#126: çok alertli senaryoda uyarılar top-3 ile sınırlı, TÜM kritikler kalır, gizli sayısı > 0."""
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=800.0))
    db.add(Account(user_id=1, name="Z", account_type=AccountType.credit_card,
                   balance=11976.0, credit_limit=12000.0))
    db.add(PersonalDebt(user_id=1, counterparty="Kirveci", direction=DebtDirection.payable,
                        amount=1500.0, is_paid=False, due_date=TODAY - timedelta(days=4)))
    # birçok uyarı kaynağı: abonelik zammı + iki kategori aşımı
    for i, a in enumerate([49.99, 49.99, 64.99]):
        db.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=a,
                           category="abonelik", description="Spotify",
                           transaction_date=TODAY - timedelta(days=70 - i * 30)))
    for cat, prev, curr in [("market", 1000, 900), ("yemek", 800, 750)]:
        db.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=prev,
                           category=cat, transaction_date=date(2026, 4, 10)))
        db.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=curr,
                           category=cat, transaction_date=TODAY - timedelta(days=3)))
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    uyari = [a for a in c["alerts"] if a["seviye"] == "uyari"]
    assert len(uyari) <= 3, f"uyarı capı 3 olmalı, {len(uyari)} bulundu"
    assert c["gizli_uyari_sayisi"] >= 1, "sığmayan uyarı sayısı raporlanmalı"
    # kritikler hiç kırpılmaz
    assert any(a["baslik"].startswith("Gecikmiş borç") for a in c["alerts"])


def test_saglikli_kullanici_tum_sinyaller_pozitif(db):
    """Sağlıklı: reel_butce > 0, daily_limit > 0, guvenli_harcama > 0, crunch yok — tutarlı."""
    db.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=20000.0))
    db.add(RecurringIncome(user_id=1, name="Maas", amount=15000.0, day_of_month=1, is_active=True))
    for i in range(6):
        db.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=100.0,
                           category="market", transaction_date=TODAY - timedelta(days=i * 2)))
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    assert c["reel_butce"] > 0 and c["daily_limit"] > 0 and c["guvenli_harcama"] > 0
    assert not [a for a in c["alerts"] if "kriz" in a["baslik"].lower()]
