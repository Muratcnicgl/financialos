"""
DATA-002 / BUG #421 KAPISI — SQLite'TA `Numeric(19,4)` PARA GİDİŞ-DÖNÜŞÜ KAYIPSIZ.

Ölçülen (12 Eyl 2026): SQLite'ın DECIMAL tipi yok; `NUMERIC` affinity değeri REAL (float64)
saklar. Madde "precision kaybı olabilir" diyordu — OLABİLİR değil, ölçülür: SQLAlchemy
`Numeric(asdecimal=True)` okuma yolunda değeri ölçeğe (4 hane) göre biçimlendirip Decimal'e
çevirir; float64'ün 53 bit anlamlısı 4 ondalık haneyi ~9×10^11'e kadar kayıpsız taşır
(kuruş hassasiyetinde ~9 trilyon TL). Bu ölçüm bunu KANITLAR; kırılırsa Integer-kuruş
göçü gündeme gelir, ondan önce değil.

Kilitlenen: 2000 rastgele + sınır değer (0,1+0,2 sınıfı, 4 ondalık, 10^11 mertebesi,
negatif) `accounts.balance`'a yazılıp okununca Decimal olarak BİREBİR eşit.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Account, AccountType, Base, User

SINIR = [Decimal("0.1"), Decimal("0.2"), Decimal("0.3"), Decimal("1.005"), Decimal("2.675"),
         Decimal("0.0001"), Decimal("-0.0001"), Decimal("123456789.9999"), Decimal("999999999999.9999"),
         Decimal("-123456.7891"), Decimal("1e-4"), Decimal("42100.10"), Decimal("7700.00")]


def test_numeric_gidis_donus_kayipsiz():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)(); s.add(User(id=1, name="u")); s.commit()
    # Deterministik "rastgele": sha256(i) — tekrar üretilebilir, ruff S311'e takılmaz
    def uret(i):
        h = int(hashlib.sha256(f"kesinlik-{i}".encode()).hexdigest(), 16)
        return Decimal(h % (2 * 10**12) - 10**12) / Decimal(10 ** (h % 5))
    degerler = SINIR + [uret(i) for i in range(2000)]
    for i, d in enumerate(degerler):
        s.add(Account(id=i + 1, user_id=1, name=f"h{i}", account_type=AccountType.cash, balance=d))
    s.commit(); s.expire_all()
    kayip = []
    for i, d in enumerate(degerler):
        okunan = s.get(Account, i + 1).balance
        assert isinstance(okunan, Decimal), type(okunan)
        if okunan.quantize(Decimal("0.0001")) != d.quantize(Decimal("0.0001")):
            kayip.append((str(d), str(okunan)))
    assert kayip == [], f"{len(kayip)} kayıp: {kayip[:5]}"
    s.close()
