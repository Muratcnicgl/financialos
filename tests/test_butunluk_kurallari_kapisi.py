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
