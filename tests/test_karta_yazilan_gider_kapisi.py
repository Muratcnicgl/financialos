"""
BUG #331 KAPISI — KARTA YAZILAN GİDER, BU AYIN NAKDİNİ AZALTMAZ.

ÖLÇÜLEN DEFEKT (4 Eylül 2026, gerçek kullanıcı verisiyle): kullanıcının yaşam giderleri
(sigara 3.600 · dışarıda yemek 4.000 · kahve 1.200 = **8.800/ay**, hepsi KREDİ KARTIYLA)
`RecurringExpense` olarak girilince nakit takvimi **"açık var: −6.906,65"** dedi.

Yanlıştı, çünkü aynı takvimde iki kalem birden nakit çıkışı sayılıyordu:

    12/09  −8.338,13   Ziraat Kredi Kartı    <- GEÇEN ayın harcamasının ödemesi
    15/09  −8.800,00   Sigara+Yemek+Kahve    <- BU ayın harcaması, yine KARTA yazılıyor

Karta yazılan bir gider bu ay nakdi AZALTMAZ: kart borcunu artırır ve **gelecek ay**
ödenir. `calculate_nakit_takvimi` giderin hangi hesaba yazıldığına hiç bakmıyordu.
Kullanıcıya olmayan bir açık gösterildi — ve bu, parası zaten sıkışık birine
"yetmeyecek" demek anlamına gelir.

BİLGİ SAKLANMIYOR: kalem takvimden ATILMAZ, `karta_yazilacak` alanında ayrı durur.
(Aynı ilke `yatirimda_bekleyen`de de uygulandı: nakde eklenmez ama görünmez de kalmaz —
BUG #320. Görünmeyen bir kalem, olmayan bir kalemden daha tehlikelidir.)

DOĞRULAMA: düzeltmeden sonra aynı veriyle takvim **ay sonu 1.893,35 · açık YOK** verdi;
bu rakam elle kurulan takvimle birebir aynı.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (Account, AccountType, Base, RecurringExpense, User)
from app.rules_engine import calculate_nakit_takvimi


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="m"))
    s.add(Account(id=1, user_id=1, name="Nakit", account_type=AccountType.cash,
                  balance=D("10000")))
    s.add(Account(id=2, user_id=1, name="Kart", account_type=AccountType.credit_card,
                  balance=D("0"), credit_limit=D("12000"), payment_day=14))
    s.commit()
    yield s
    s.close()


def _gider(db, ad, tutar, hesap_id, gun=15):
    db.add(RecurringExpense(user_id=1, name=ad, amount=D(str(tutar)),
                            account_id=hesap_id, day_of_month=gun, is_active=True))
    db.commit()


def test_KARTA_yazilan_gider_nakit_cikisi_SAYILMAZ(db):
    _gider(db, "Sigara", 3600, hesap_id=2)          # kart
    t = calculate_nakit_takvimi(1, db, date(2026, 9, 4))
    assert all(k["ad"] != "Sigara" for k in t["kalemler"]), \
        "karta yazılan gider nakit takvimine çıkış olarak girdi"
    assert t["ay_sonu_bakiye"] == D("10000"), t["ay_sonu_bakiye"]


def test_NAKITTEN_odenen_gider_HALA_nakit_cikisidir(db):
    """Düzeltme kapsamı DAR: yalnız kredi kartı. Nakit/banka gideri eskisi gibi düşer."""
    _gider(db, "Kira", 5000, hesap_id=1)            # nakit
    t = calculate_nakit_takvimi(1, db, date(2026, 9, 4))
    assert any(k["ad"] == "Kira" for k in t["kalemler"])
    assert t["ay_sonu_bakiye"] == D("5000"), t["ay_sonu_bakiye"]


def test_KART_GIDERI_GORUNMEZ_OLMAZ_ayri_alanda_durur(db):
    """
    Takvimden çıkarmak, yok saymak DEĞİLDİR. Kalem `karta_yazilacak`ta durur ki koç
    "bu ay 3.600 TL daha kart borcu birikecek" diyebilsin. (BUG #320'nin aynı ilkesi.)
    """
    _gider(db, "Sigara", 3600, hesap_id=2)
    _gider(db, "Kahve", 1200, hesap_id=2)
    t = calculate_nakit_takvimi(1, db, date(2026, 9, 4))
    assert t["karta_yazilacak_toplam"] == D("4800"), t["karta_yazilacak_toplam"]
    adlar = {k["ad"] for k in t["karta_yazilacak"]}
    assert adlar == {"Sigara", "Kahve"}, adlar


def test_PASIF_gider_hicbir_yerde_gorunmez(db):
    _gider(db, "Sigara", 3600, hesap_id=2)
    db.query(RecurringExpense).update({"is_active": False})
    db.commit()
    t = calculate_nakit_takvimi(1, db, date(2026, 9, 4))
    assert t["karta_yazilacak"] == [] and t["karta_yazilacak_toplam"] == D("0")


def test_SAHTE_ACIK_uretilmiyor(db):
    """
    Bugünkü defektin uçtan uca hâli: kart ödemesi + karta yazılan gider birlikteyken
    açık ÜRETİLMEMELİ.
    """
    kart = db.get(Account, 2)
    kart.balance = D("8338.13")     # ödenecek kart borcu (geçen ayın harcaması)
    db.commit()
    _gider(db, "Sigara", 3600, hesap_id=2)
    _gider(db, "Dışarıda yemek", 4000, hesap_id=2)
    _gider(db, "Kahve", 1200, hesap_id=2)
    t = calculate_nakit_takvimi(1, db, date(2026, 9, 4))
    assert t["acik_var"] is False, (t["ay_sonu_bakiye"], t["en_dusuk_bakiye"])
    assert t["ay_sonu_bakiye"] == D("1661.87"), t["ay_sonu_bakiye"]   # 10.000 − 8.338,13
