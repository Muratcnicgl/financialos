"""
PERF-002 (BUG #487): onay ucu önce/sonra farkı için tam kokpiti iki kez üretmez.

Ölçüm (14 Eyl 2026): `approve_action` `generate_cockpit`i iki kez çağırıyor, sonuçtan yalnız
`net_deger` ve `nakit_kasa` okuyordu. `hizli_bakiye_ozeti` tek hesap sorgusuyla aynı iki
sayıyı verir. Kilitlenen: (1) hızlı özet, kokpitle beş hesap tipinde (nakit, kart, kredi,
yatırım, emanet yatırım) AYNI sayıları verir; (2) onay ucu artık `generate_cockpit` çağırmaz;
(3) hızlı yol ölçülebilir biçimde ucuz (sorgu sayısı: 1).
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Account, AccountType, Base, User
from app.rules_engine import generate_cockpit, hizli_bakiye_ozeti

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="t"))
    s.add_all([
        Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=12345.67),
        Account(user_id=1, name="Nakit2", account_type=AccountType.cash, balance=1000),
        Account(user_id=1, name="Kart", account_type=AccountType.credit_card, balance=4321.5, credit_limit=20000),
        Account(user_id=1, name="Kredi", account_type=AccountType.loan, balance=50000, monthly_payment=2500, remaining_installments=20),
        Account(user_id=1, name="Fon", account_type=AccountType.investment, balance=0, lot_count=10.5, current_price=123.4567, cost_per_lot=100),
        Account(user_id=1, name="Emanet", account_type=AccountType.investment, balance=0, lot_count=3, current_price=1000, is_emanet=True),
    ])
    s.commit()
    yield s, eng
    s.close()


def test_hizli_ozet_kokpitle_ayni(db):
    s, _ = db
    kokpit = generate_cockpit(1, date(2026, 9, 14), s)
    hizli = hizli_bakiye_ozeti(1, s)
    assert hizli["nakit_kasa"] == pytest.approx(kokpit["nakit_kasa"], abs=0.005)
    assert hizli["net_deger"] == pytest.approx(kokpit["net_deger"], abs=0.005)
    # emanet net değere girmez — kopya bunu unutursa kırılır
    assert kokpit["emanet_kasa"] == 3000
    assert hizli["net_deger"] == pytest.approx(12345.67 + 1000 + 10.5 * 123.4567 - 4321.5 - 50000, abs=0.01)


def test_hizli_ozet_tek_sorgu(db):
    s, eng = db
    sayac = []

    def dinle(conn, cursor, statement, *_):
        sayac.append(statement)

    event.listen(eng, "before_cursor_execute", dinle)
    try:
        hizli_bakiye_ozeti(1, s)
    finally:
        event.remove(eng, "before_cursor_execute", dinle)
    secmeler = [q for q in sayac if q.lstrip().upper().startswith("SELECT")]
    assert len(secmeler) == 1, f"hızlı özet {len(secmeler)} sorgu attı: {secmeler}"


def test_onay_ucu_tam_kokpit_uretmez():
    src = (KOK / "app" / "routers" / "actions.py").read_text(encoding="utf-8")
    assert "hizli_bakiye_ozeti(current_user.id, db)" in src
    assert re.search(r"^\s*cockpit_(before|after) = generate_cockpit", src, re.M) is None, "onay ucu hâlâ tam kokpit üretiyor"
