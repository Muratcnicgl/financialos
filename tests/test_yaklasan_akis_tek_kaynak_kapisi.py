"""
PERF-017 / BUG #442 KAPISI — YAKLAŞAN AKIŞ VE NAKİT TAHMİNİ AYNI PROJEKSİYONU KULLANIR.

Ölçülen (13 Eyl 2026): `reports.upcoming-cashflow` kredi taksiti ve düzenli gelir/gider
genişletmesinin İKİNCİ bir kopyasını taşıyordu (`_next_occurrences` `_month_occurrences`'ın
harfi harfine kopyasıydı) ve tahminden iki kusurda ayrışıyordu: kalan taksit `None` (rapor
sınırsız, tahmin 0 → kredi tahminden kayboluyordu) ve geçmiş vadeli kredi (rapor geçmiş
tarihleri "yaklaşan" listeliyordu).

Kilitlenen: aynı veri için iki ucun kredi+düzenli kalemleri (tarih, tutar) birebir; `None`
taksit ufuk içinde her ay taksit üretir, 0 üretmez; geçmiş vadeli kredi raporda geçmiş tarih
göstermez; rapor gecikmiş alacağı bilinçli olarak GÖSTERİR (belgeli fark).
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.cashflow import _expand_loan_payments, generate_forecast
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import (Account, AccountType, DebtDirection, PersonalDebt, RecurringExpense,
                        RecurringIncome)

BUGUN = date(2026, 9, 13)


def _kur(db, uid):
    db.add(Account(user_id=uid, name="Nakit", account_type=AccountType.cash, balance=5000))
    db.add(Account(user_id=uid, name="Konut", account_type=AccountType.loan, balance=90000,
                   monthly_payment=3000, next_payment_date=date(2026, 9, 20), remaining_installments=None))
    db.add(Account(user_id=uid, name="Eski", account_type=AccountType.loan, balance=9000,
                   monthly_payment=1000, next_payment_date=date(2026, 7, 5), remaining_installments=3))
    db.add(RecurringIncome(user_id=uid, name="Maaş", amount=40000, day_of_month=1, is_active=True))
    db.add(RecurringExpense(user_id=uid, name="Kira", amount=15000, day_of_month=10, is_active=True))
    db.add(PersonalDebt(user_id=uid, counterparty="A", amount=500, direction=DebtDirection.receivable,
                        due_date=date(2026, 9, 1), is_paid=False))   # GECİKMİŞ alacak
    db.commit()


def test_none_taksit_ufukta_her_ay_sifir_hic():
    kredi = Account(name="K", account_type=AccountType.loan, monthly_payment=100,
                    next_payment_date=date(2026, 9, 20), remaining_installments=None)
    assert [e.date for e in _expand_loan_payments(kredi, BUGUN, BUGUN + timedelta(days=90))] == \
        [date(2026, 9, 20), date(2026, 10, 20), date(2026, 11, 20)]   # ufuk 12 Ara
    kredi.remaining_installments = 0
    assert _expand_loan_payments(kredi, BUGUN, BUGUN + timedelta(days=90)) == []


def test_iki_uc_ayni_projeksiyon(db_session, test_user, monkeypatch):
    _kur(db_session, test_user.id)
    monkeypatch.setattr("app.routers.reports.user_today", lambda u: BUGUN)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        rapor = TestClient(app).get("/api/reports/upcoming-cashflow?days=60").json()["items"]
    finally:
        app.dependency_overrides.clear()
    tahmin = generate_forecast(db_session, test_user.id, horizon_days=61, today=BUGUN)
    tahmin_olaylar = sorted((e.date.isoformat(), round(float(e.amount), 2)) for g in tahmin["days"] for e in g.events
                            if e.source_type in ("income", "recurring_expense", "loan_payment"))
    rapor_olaylar = sorted((i["date"], round(float(i["amount"]), 2)) for i in rapor
                           if i["source"] in ("income", "recurring_expense", "loan"))
    assert rapor_olaylar == tahmin_olaylar, (rapor_olaylar, tahmin_olaylar)
    # None taksitli kredi iki uçta da ufuk boyunca var; geçmiş vadeli kredi geçmiş tarih göstermez
    assert sum(1 for i in rapor if i["label"] == "Konut") == 2
    assert all(i["date"] >= BUGUN.isoformat() for i in rapor if i["source"] == "loan")
    # Belgeli fark: rapor gecikmiş alacağı gösterir, tahmin göstermez
    assert any(i["source"] == "personal_debt" and i["date"] < BUGUN.isoformat() for i in rapor)
    assert not any(e.source_type == "receivable" for g in tahmin["days"] for e in g.events)
