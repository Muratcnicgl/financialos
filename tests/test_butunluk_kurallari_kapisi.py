"""
DATA-025 / DATA-029 / BUG #444 KAPISI — ORM BÜTÜNLÜK KURALLARI FLUSH'TA UYGULANIR.

Ölçülen (13 Eyl 2026): canlı veride ihlal 0/0 ama kural yoktu — dört test fikstürü bile
`is_paid=True, paid_date=None` yazıyordu (kapı ilk koşumda yakaladı). DB CHECK yerine ORM
`before_flush` (SQLite'ta CHECK eklemek tablo yeniden kurulumu ister; bilinçli kaçınıldı).

Kilitlenen: tutarsız PersonalDebt (ödendi/tarih) ve bozuk `YYYY-MM` dedup anahtarı flush'a
giremez, mesaj alanı söyler; tutarlı satır geçer; silme yolu (is_paid=False + tarihli satır
silinirken) kural yüzünden kırılmaz; kanca uygulama başlangıcında bağlı.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.butunluk as butunluk
from app.models import Base, DebtDirection, PersonalDebt, RecurringIncome, User


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)(); ses.add(User(id=1, name="u")); ses.commit()
    yield ses; ses.close()


def _borc(**k):
    v = dict(user_id=1, counterparty="A", amount=100, direction=DebtDirection.receivable, due_date=date(2026, 9, 1),
             is_paid=False)
    v.update(k); return PersonalDebt(**v)


def test_odendi_tarihsiz_ve_tarihli_odenmedi_reddedilir(s):
    s.add(_borc(is_paid=True))
    with pytest.raises(butunluk.ButunlukHatasi, match="is_paid=True ile paid_date=None"):
        s.commit()
    s.rollback()
    s.add(_borc(is_paid=False, paid_date=date(2026, 9, 2)))
    with pytest.raises(butunluk.ButunlukHatasi):
        s.commit()
    s.rollback()
    s.add(_borc(is_paid=True, paid_date=date(2026, 9, 2))); s.commit()
    assert s.query(PersonalDebt).count() == 1


def test_guncellemede_de_uygulanir_ve_silme_yolu_kirilmaz(s):
    b = _borc(is_paid=True, paid_date=date(2026, 9, 2)); s.add(b); s.commit()
    b.paid_date = None
    with pytest.raises(butunluk.ButunlukHatasi):
        s.flush()
    s.rollback()
    b = s.query(PersonalDebt).one()
    b.is_paid = False; b.paid_date = None   # debts.delete yolu: ikisi birlikte sıfırlanır
    s.delete(b); s.commit()
    assert s.query(PersonalDebt).count() == 0


@pytest.mark.parametrize("ym,gecer", [("2026-09", True), (None, True), ("2026-9", False),
                                       ("May-26", False), ("2026-13", False), ("2026-09-01", False)])
def test_dedup_anahtari_bicimi(s, ym, gecer):
    s.add(RecurringIncome(user_id=1, name="Maaş", amount=1, day_of_month=1, is_active=True,
                          last_triggered_year_month=ym))
    if gecer:
        s.commit()
    else:
        with pytest.raises(butunluk.ButunlukHatasi, match="YYYY-MM"):
            s.commit()
        s.rollback()


def test_kanca_uygulamada_bagli():
    src = (__import__("pathlib").Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "from app import butunluk" in src


def test_icgoru_durumu_ucuncu_deger_olamaz(s):
    """DATA-019: sütun nullable ama NULL bir durum değildir; yeni nesnede None = varsayılan."""
    from app.models import CoachInsight
    i = CoachInsight(user_id=1, insight_type="pattern", title="t", content="c")
    s.add(i); s.commit()
    assert i.status == "active", "INSERT'te sütun varsayılanı yazılmalı"
    i.status = None
    with pytest.raises(butunluk.ButunlukHatasi, match="NULL üçüncü durum değildir"):
        s.commit()
    s.rollback()
    i = s.query(CoachInsight).one()
    i.status = "bilinmeyen"
    with pytest.raises(butunluk.ButunlukHatasi):
        s.commit()
    s.rollback()
    i = s.query(CoachInsight).one()
    i.status = "dormant"; s.commit()


def test_hedef_ilerlemesi_sifir_yuz_araliginda(s):
    """DATA-033: goal_engine klempliyor ama tek yazıcı değil; kural flush'ta."""
    from app.models import Goal
    g = Goal(user_id=1, title="Tatil", goal_type="savings", target_amount=1000, progress_percent=0)
    s.add(g); s.commit()
    for kotu in (-1, 100.01):
        g.progress_percent = kotu
        with pytest.raises(butunluk.ButunlukHatasi, match=r"\[0, 100\]"):
            s.commit()
        s.rollback(); g = s.query(Goal).one()
    g.progress_percent = 100; s.commit()


def test_kart_alanlari_yalniz_kartta_ve_uc_422_doner(s):
    """DATA-027 / BUG #447: nakit hesapta kart alanı dolu olamaz; kural API'den 422 olarak görünür."""
    from fastapi.testclient import TestClient
    from app.dependencies import get_current_user, get_db
    from app.main import app
    from app.models import Account, AccountType
    s.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card, balance=0,
                  credit_limit=10000, statement_day=5, payment_day=15)); s.commit()   # kartta serbest
    s.add(Account(user_id=1, name="Kart2", account_type=AccountType.credit_card, balance=0)); s.commit()  # limitsiz kart da geçer (L45)
    s.add(Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=0, statement_day=5))
    with pytest.raises(butunluk.ButunlukHatasi, match="statement_day"):
        s.commit()
    s.rollback()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        r = TestClient(app).post("/api/accounts", json={"name": "N", "account_type": "cash", "balance": 0, "credit_limit": 500})
        assert r.status_code == 422, r.text
        assert "kart alanı" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()
