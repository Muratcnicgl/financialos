"""
RULE-030 / BUG #432 KAPISI — NAKİT PROJEKSİYONU KAPSAMINI SÖYLER, KART TAMPONUNU AYRI VERİR.

Ölçülen (12 Eyl 2026): `generate_forecast` yalnız nakit hesapları izler (kart döngüsü
modelde yok); "kriz yok" hükmü nakit üzerinden. Kart %99 doluyken nakit pozitifse sessizce
"kriz yok" diyordu, kapsam hiçbir yerde yazmıyordu. Kart limitini bakiyeye EKLEMEK yanlış
olurdu (borç); ayrı alan olarak raporlanır, arayüz kapsamı ve köprüyü söyler.

Kilitlenen: `summary.kapsam == "nakit"`; `kalan_kart_limiti` = Σ max(0, limit − borç), limitli
kart yoksa None (0 değil, L45); limiti aşan kart 0 katkı; opening_balance karttan ETKİLENMEZ;
başka kullanıcının kartı sayılmaz.
"""
from __future__ import annotations

from datetime import date

from app.cashflow import generate_forecast
from app.models import Account, AccountType, User

BUGUN = date(2026, 9, 12)


def _kart(db, user_id, limit, borc):
    db.add(Account(user_id=user_id, name="k", account_type=AccountType.credit_card,
                   balance=borc, credit_limit=limit)); db.commit()


def test_kapsam_ve_kart_yokken_None(db_session, test_user):
    db_session.add(Account(user_id=test_user.id, name="n", account_type=AccountType.cash, balance=1000)); db_session.commit()
    o = generate_forecast(db_session, test_user.id, horizon_days=7, today=BUGUN)["summary"]
    assert o["kapsam"] == "nakit"
    assert o["kalan_kart_limiti"] is None, "limitli kart yok → bilinmez, sıfır değil"
    assert o["opening_balance"] == 1000


def test_kalan_limit_toplami_ve_asan_kart_sifir(db_session, test_user):
    db_session.add(Account(user_id=test_user.id, name="n", account_type=AccountType.cash, balance=1000)); db_session.commit()
    _kart(db_session, test_user.id, 10000, 4000)     # 6000 kalan
    _kart(db_session, test_user.id, 5000, 5300)      # aşmış → 0
    _kart(db_session, test_user.id, None, 700)       # limitsiz → sayılmaz
    o = generate_forecast(db_session, test_user.id, horizon_days=7, today=BUGUN)["summary"]
    assert o["kalan_kart_limiti"] == 6000
    assert o["opening_balance"] == 1000, "kart limiti nakit bakiyeye EKLENMEZ"


def test_baska_kullanicinin_karti_sayilmaz(db_session, test_user):
    db_session.add(Account(user_id=test_user.id, name="n", account_type=AccountType.cash, balance=0)); db_session.commit()
    diger = User(name="diger"); db_session.add(diger); db_session.commit()
    _kart(db_session, diger.id, 10000, 0)
    assert generate_forecast(db_session, test_user.id, horizon_days=7, today=BUGUN)["summary"]["kalan_kart_limiti"] is None
