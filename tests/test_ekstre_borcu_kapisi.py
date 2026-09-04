"""
BUG #337 KAPISI — BİR KARTIN DA İKİ SAYISI VARDIR (BUG #318'in kart karşılığı).

ÖLÇÜLEN DEFEKT (4 Eylül 2026, Ziraat ekranından birebir):

    Son Ekstreden Kalan Borç : 8.221,13   <- ASGARİ BUNUN yüzdesidir
    Güncel Borç              : 8.338,13   <- `balance` bu (veri modeli kuralı, doğru)

Asgari ödeme **ekstre** borcunun %20'sidir: 8.221,13 × %20 = **1.644,23** (bankanın
ekranında yazan). Ürün `balance` (güncel borç) kullandığı için **1.667,63** hesaplıyordu —
23,40 TL fark. Bugün küçük, ama YÖN yanlış: ekstre kesildikten sonra yapılan her harcama
asgariyi olduğundan büyük gösterir, ve ay içinde kart ne kadar kullanılırsa fark o kadar
büyür.

Bu, BUG #318'in aynı sınıfı: bir hesabın karar verdiren İKİ sayısı varsa ikisi de SAYISAL
alan olmalıdır. Kredide `balance` (kalan taksit toplamı) ↔ `early_payoff_amount`;
kartta `balance` (güncel borç) ↔ `statement_balance` (son ekstreden kalan).

NULL = BİLİNMİYOR → `balance`e düşülür (davranış değişmez, L45). Göç geriye dönük
DOLDURMAZ: ekstre borcunu yalnız banka bilir; `balance`ten türetmek ölçmediğimiz bir
sayıyı doğruymuş gibi sunmak olurdu.
"""
from __future__ import annotations

from decimal import Decimal as D

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.debt_strategy import collect_debts
from app.models import Account, AccountType, Base, User


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="m"))
    s.commit()
    yield s
    s.close()


def _kart(db, guncel="8338.13", ekstre=None, oran=0.20):
    db.add(Account(id=1, user_id=1, name="Kart", account_type=AccountType.credit_card,
                   balance=D(guncel), credit_limit=D("12000"),
                   statement_balance=D(ekstre) if ekstre is not None else None,
                   min_payment_ratio=oran))
    db.commit()


def test_ASGARI_EKSTRE_borcundan_hesaplanir(db):
    """Bankanın ekranındaki gerçek: 8.221,13 × %20 = 1.644,23."""
    _kart(db, guncel="8338.13", ekstre="8221.13")
    assert abs(collect_debts(db, 1)[0].min_payment - 1644.23) < 0.01


def test_EKSTRE_YOKSA_guncel_borca_dusulur(db):
    """Geriye uyum: ekstre bilinmiyorsa eski davranış (L45 — bilinmeyen, yedek)."""
    _kart(db, guncel="8338.13", ekstre=None)
    assert abs(collect_debts(db, 1)[0].min_payment - 8338.13 * 0.20) < 0.01


def test_BAKIYE_hala_GUNCEL_borctur(db):
    """
    Ekstre alanı `balance`in anlamını DEĞİŞTİRMEZ. `balance` = güncel borç kalır
    (veri modeli kuralı); borç motoru onu faizlendirir ve nakit takvimi onu öder.
    Karıştırmak, BUG #318'in kartlardaki tekrarı olurdu.
    """
    _kart(db, guncel="8338.13", ekstre="8221.13")
    assert abs(collect_debts(db, 1)[0].balance - 8338.13) < 0.01


def test_EKSTRE_SIFIR_gecerli_bir_degerdir(db):
    """
    "Son ekstre kapandı" gerçek bir durumdur (1 Eylül'de tam olarak böyleydi: ekstre 0,00
    ama güncel borç 8.221,13). Sıfır, "bilinmiyor" ile KARIŞTIRILMAMALI — asgari 0 olur.
    """
    _kart(db, guncel="8338.13", ekstre="0")
    assert collect_debts(db, 1)[0].min_payment == 50.0     # taban: max(0, 50)


def test_CANLI_KARTTA_ekstre_yazili():
    """Ürün düzeltmesi kadar bir VERİ düzeltmesi: canlı kart ekstre borcunu taşımalı."""
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent
    if not (kok / "data" / "financialos.db").exists():
        pytest.skip("canlı DB yok")
    import sqlite3
    c = sqlite3.connect(kok / "data" / "financialos.db")
    try:
        satir = c.execute(
            "select statement_balance from accounts "
            "where user_id=5 and name like 'Ziraat Kredi Kart%'").fetchone()
    finally:
        c.close()
    assert satir and abs(float(satir[0]) - 8221.13) < 0.01, \
        f"canlı kartta ekstre borcu {satir} — 8.221,13 olmalı (banka ekranı)"
