"""
D08 (BUG #229) — OTOMATİK FİYAT CRON'U `Account.balance`'I GÜNCELLEMİYORDU.

Kullanıcı aynı uygulamada aynı yatırım hesabı için İKİ FARKLI TL rakamı görüyordu:
Cockpit 36.000, Hesaplar paneli 30.000 — üstelik aynı kartta "6 lot × 6.000 TL" de yazıyor.
Hangisinin doğru olduğunu bilmesinin yolu yok. Finansal üründe birbiriyle çelişen bakiye =
yanlış rakama göre satış/harcama kararı + ürüne güvenin bir defada bitmesi.

Kök neden bir DEĞİŞMEZ İHLALİ: `balance == lot_count × current_price` (yatırım hesapları için)
diğer TÜM yazma yollarında korunuyordu — `fund_tracker` (manuel fiyat), `routers/accounts`
(create/update), `action_executor` (BUG #102 yorumu bu değişmezi açıkça adlandırıyor),
`simulation_engine`. Tek ihlal eden yol gece koşan fiyat cron'uydu: `current_price` yazılıp
`balance` bayat bırakılıyordu. Okuma tarafı ayrışık: cockpit `lot × fiyat` hesaplar,
`/api/accounts` ham `balance` döner.

Hiçbir test bu senkronu doğrulamıyordu; dahası `tests/test_stock_price_isyatirim_m_hisse.py`
sapmayı (`balance=0` iken cockpit 3295) yeşil bir teste gömüyordu.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Account, AccountType
from app.price_providers.router import record_investment_price
from app.rules_engine import generate_cockpit


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def kullanici(db):
    u = User(name="murat", email="m@x.com")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def fon_hesabi(db, kullanici):
    a = Account(user_id=kullanici.id, name="TLY Fon", account_type=AccountType.investment,
                fund_code="TLY", lot_count=6.0, current_price=5000.0, balance=30000.0)
    db.add(a)
    db.commit()
    return a


@pytest.fixture
def client(db, kullanici):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: kullanici
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_cron_fiyat_yazinca_bakiye_de_guncellenir(db, fon_hesabi):
    """Değişmez: yatırım hesabında `balance == lot × current_price` (denetim D08)."""
    record_investment_price(db, fon_hesabi, Decimal("6000"), "tefas")
    db.refresh(fon_hesabi)
    assert float(fon_hesabi.balance) == pytest.approx(36000.0), (
        f"Cron fiyatı yazdı ama bakiye {fon_hesabi.balance} kaldı — Hesaplar paneli "
        "kalıcı olarak bayat rakam gösterir"
    )


def test_iki_panel_ayni_hesap_icin_ayni_parayi_gosterir(client, db, kullanici, fon_hesabi):
    """Kullanıcı-görünür sözleşme: Cockpit ve Hesaplar aynı hesapta aynı TL'yi göstermeli."""
    record_investment_price(db, fon_hesabi, Decimal("6000"), "tefas")

    hesaplar = client.get("/api/accounts").json()
    hesap = next(h for h in hesaplar if h["name"] == "TLY Fon")
    cockpit = generate_cockpit(kullanici.id, date.today(), db)
    cockpit_hesap = next(h for h in cockpit["accounts"] if h["ad"] == "TLY Fon")

    assert float(hesap["balance"]) == pytest.approx(float(cockpit_hesap["bakiye"])), (
        f"Hesaplar paneli {hesap['balance']} TL, Cockpit {cockpit_hesap['bakiye']} TL — "
        "aynı hesap için çelişen iki rakam"
    )


def test_lot_bilinmiyorsa_bakiyeye_dokunulmaz(db, kullanici):
    """`lot_count` yoksa `lot × fiyat` hesaplanamaz — bakiyeyi 0'a düşürmek veri kaybı olurdu."""
    a = Account(user_id=kullanici.id, name="Lotsuz", account_type=AccountType.investment,
                fund_code="XXX", lot_count=None, current_price=100.0, balance=12345.0)
    db.add(a)
    db.commit()

    record_investment_price(db, a, Decimal("200"), "tefas")
    db.refresh(a)
    assert float(a.balance) == pytest.approx(12345.0), \
        "Lot bilinmezken bakiye ezildi (veri kaybı)"
    assert float(a.current_price) == pytest.approx(200.0), "Fiyat yine de kaydedilmeli"


def test_sifir_lot_bakiyeyi_sifirlar(db, kullanici):
    """Pozisyon kapandıysa (lot=0) bakiye 0 olmalı — değişmezin doğal sonucu."""
    a = Account(user_id=kullanici.id, name="Kapali", account_type=AccountType.investment,
                fund_code="YYY", lot_count=0.0, current_price=100.0, balance=5000.0)
    db.add(a)
    db.commit()

    record_investment_price(db, a, Decimal("150"), "tefas")
    db.refresh(a)
    assert float(a.balance) == pytest.approx(0.0), \
        "Lot 0 iken bakiye eski değerde kaldı (kapanmış pozisyon para gösteriyor)"


def test_fiyat_gecmisi_ve_zaman_damgasi_bozulmadi(db, fon_hesabi):
    """Regresyon: bakiye senkronu, cron'un asıl işini (PriceHistory + damga) bozmamalı."""
    from app.models import PriceHistory
    yeni = record_investment_price(db, fon_hesabi, Decimal("6000"), "tefas")
    db.refresh(fon_hesabi)
    assert yeni is True
    assert float(fon_hesabi.current_price) == pytest.approx(6000.0)
    assert fon_hesabi.last_price_update is not None
    kayit = db.query(PriceHistory).filter(PriceHistory.fund_code == "TLY").one()
    assert float(kayit.close_price) == pytest.approx(6000.0)


def test_yatirim_disi_hesap_etkilenmez(db, kullanici):
    """Nakit/kart hesabında `lot × fiyat` değişmezi YOKTUR — bakiyeye dokunulmamalı."""
    a = Account(user_id=kullanici.id, name="Nakit", account_type=AccountType.cash,
                fund_code="TRY", lot_count=3.0, current_price=2.0, balance=9999.0)
    db.add(a)
    db.commit()

    record_investment_price(db, a, Decimal("4"), "fx")
    db.refresh(a)
    assert float(a.balance) == pytest.approx(9999.0), \
        "Yatırım olmayan hesabın bakiyesi lot×fiyat ile ezildi"
