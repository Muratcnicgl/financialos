"""
SİSTEM KATEGORİSİ DIŞLAMASI HER İKİ ANALİZDE DE GEÇERLİ — ADR-046 kapsam boşluğu.

ÖLÇÜLEN DEFEKT (10 Eyl 2026, gerçek kullanıcı verisi): ekranda şu uyarı vardı —
    "Kategori aşım öngörüsü: borc_odeme — bu gidişle ay sonu ~4.932,69 TL olur
     (geçen ay 2.242,99 TL, %119.9 fazla). HIZ KES."
`borc_odeme` bir SİSTEM kategorisidir (muhasebe işlemi, kişisel harcama değil). Kart
borcunu daha çok ödemek İYİ bir şeydir; "hız kes" tam ters tavsiyedir. Üstelik bu tavsiye
koçun bağlamına da giriyordu.

ADR-046 (BUG #264) bu dışlamayı zaten tanımlamış ve `category_rules.sistem_slug_kumesi`
tek kaynağını kurmuştu. Ama yalnız `_spending_patterns`e ("Davranış Kalıpları") bağlanmıştı;
kardeşi `_category_overspend_alerts` (FEAT-005 projeksiyon uyarısı) filtresiz kaldı. Aynı
soruyu soran iki analizden biri filtreli, öteki değildi — ve boşluk SESSİZDİ, çünkü hiçbir
test "bu kural her iki yolda da geçerli mi" diye sormuyordu.

Bu kapı kuralı DEĞİL, KAPSAMI ölçer: sistem kategorisi hangi analizden geçerse geçsin
kişisel harcama artışı sayılmaz.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Account, AccountType, Transaction, TransactionType, User
from app.rules_engine import _calculate_category_patterns, _category_overspend_alerts

BUGUN = date(2026, 9, 10)


@pytest.fixture
def db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="kullanici"))
    s.add(Account(id=1, user_id=1, name="Nakit", account_type=AccountType.cash,
                  balance=10000.0))
    s.commit()
    yield s
    s.close()


def _gider(db, tarih: date, tutar: float, kategori: str):
    db.add(Transaction(user_id=1, account_id=1, transaction_type=TransactionType.expense,
                       amount=tutar, category=kategori, transaction_date=tarih))
    db.commit()


def _iki_kat_harcama(db, kategori: str):
    """Geçen ay 1.000, bu ay ilk 10 günde 1.600 → projeksiyon geçen ayın çok üstünde."""
    _gider(db, date(2026, 8, 15), 1000.0, kategori)
    _gider(db, date(2026, 9, 5), 1600.0, kategori)


def test_KISISEL_kategori_asim_uyarisi_URETIR(db):
    """Kapının kendisi çalışıyor mu — yoksa 'hiç uyarı yok' sahte yeşil olur (ders L28)."""
    _iki_kat_harcama(db, "market")
    uyarilar = _category_overspend_alerts(1, BUGUN, db)
    assert any("market" in u["baslik"] for u in uyarilar), \
        "kişisel kategoride uyarı üretilmiyor — test ölçmek istediğini ölçmüyor"


@pytest.mark.parametrize("sistem_kategori", ["borc_odeme", "kredi_taksiti", "transfer"])
def test_SISTEM_kategorisi_asim_uyarisi_URETMEZ(db, sistem_kategori):
    """Bildirilen defekt: borç ödemesine 'hız kes' demek ters tavsiyedir."""
    _iki_kat_harcama(db, sistem_kategori)
    uyarilar = _category_overspend_alerts(1, BUGUN, db)
    assert not any(sistem_kategori in u["baslik"] for u in uyarilar), \
        f"sistem kategorisi '{sistem_kategori}' harcama artışı sayıldı (ADR-046 ihlali)"


def test_ayni_dislama_KARDES_analizde_de_gecerli(db):
    """Kapsam kapısı: kural tek yolda değil, HER iki yolda da geçerli olmalı."""
    _gider(db, BUGUN - timedelta(days=40), 1000.0, "borc_odeme")
    _gider(db, BUGUN - timedelta(days=5), 2000.0, "borc_odeme")
    _gider(db, BUGUN - timedelta(days=4), 500.0, "borc_odeme")
    _gider(db, BUGUN - timedelta(days=3), 500.0, "borc_odeme")

    patern_kategorileri = {p.get("category") for p in _calculate_category_patterns(1, BUGUN, db)}
    asim_baslıklari = " ".join(u["baslik"] for u in _category_overspend_alerts(1, BUGUN, db))

    assert "borc_odeme" not in patern_kategorileri, "davranış kalıbı dışlaması bozulmuş"
    assert "borc_odeme" not in asim_baslıklari, "aşım öngörüsü dışlaması bozulmuş"
