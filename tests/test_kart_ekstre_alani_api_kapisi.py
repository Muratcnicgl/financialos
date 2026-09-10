"""
KART EKSTRE ALANLARI API'DEN YAZILABİLİR KAPISI — "sessiz no-op" sınıfı.

NEDEN VAR (ölçülen defekt, 10 Eyl 2026): `Account.statement_balance` ve
`Account.min_payment_ratio` VERİ MODELİNDE aylardır vardı (BUG #337, BUG #330) ve motor
ikisini de okuyordu; ama API şemasında (`routers/accounts.AccountUpdate`) TANIMLI DEĞİLDİ.
Gerçek kart verisi girilirken PUT gövdesine kondu, **200 döndü ve hiçbir şey yazılmadı** —
Pydantic bilinmeyen alanı sessizce atar. İstemci "yazdım" sandı; motor ekstre borcunu
göremeyip güncel borcu, bankanın asgari oranını göremeyip koddaki yedek oranı kullanmaya
devam etti. Yazılamayan bir alan, olmayan bir alandır.

Tuzağın ikinci yarısı: `AccountBase`/`AccountUpdate` İKİ KEZ tanımlıydı — biri
`app/schemas.py`de (hiçbir yerden import edilmiyor), biri `app/routers/accounts.py`de
(gerçekten kullanılan). İlk düzeltme ölü kopyaya yapıldı ve hiçbir şey değişmedi. Bu kapı
davranışı ÇALIŞAN UÇTAN ölçer; hangi sınıfın düzenlendiğine bakmaz.

KİLİTLENEN DEĞİŞMEZLER:
  1. POST ile yaratırken iki alan da kalıcı olur.
  2. PUT ile güncellerken iki alan da kalıcı olur (200 dönüp yutmaz).
  3. Alanlar okuma yanıtında (AccountOut) GERİ DÖNER — yazılıp okunamayan alan yarımdır.
  4. statement_balance = 0 geçerlidir ("ekstre kapandı") ve None'a çevrilmez.
  5. min_payment_ratio 0-1 aralığı dışındaysa REDDEDİLİR (422) — %20 yerine 20 yazılırsa
     asgari 100 kat büyür; sessizce kabul etmek para hatasıdır.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_db, get_current_user
from app.main import app
from app.models import Account, AccountType, User


@pytest.fixture
def db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="kullanici"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _kart(db, **kw):
    a = Account(user_id=1, name="Kart A", account_type=AccountType.credit_card,
                balance=10020.75, credit_limit=12000.0, statement_day=2, payment_day=12, **kw)
    db.add(a); db.commit(); db.refresh(a)
    return a


def test_POST_ile_yaratirken_kalici_olur(client, db):
    r = client.post("/api/accounts", json={
        "name": "Kart A", "account_type": "credit_card", "balance": 10020.75,
        "credit_limit": 12000, "statement_day": 2, "payment_day": 12,
        "statement_balance": 6576.90, "min_payment_ratio": 0.20,
    })
    assert r.status_code == 201, r.text
    acc = db.get(Account, r.json()["id"])
    assert float(acc.statement_balance) == 6576.90
    assert acc.min_payment_ratio == 0.20


def test_PUT_200_donup_YUTMAZ(client, db):
    """Bildirilen defektin ta kendisi: 200 dönüyor, DB değişmiyordu."""
    kart = _kart(db)
    assert kart.statement_balance is None          # başlangıçta bilinmiyor
    r = client.put(f"/api/accounts/{kart.id}",
                   json={"statement_balance": 6576.90, "min_payment_ratio": 0.20})
    assert r.status_code == 200, r.text
    db.refresh(kart)
    assert float(kart.statement_balance) == 6576.90, "PUT 200 döndü ama yazmadı"
    assert kart.min_payment_ratio == 0.20


def test_okuma_yanitinda_geri_doner(client, db):
    kart = _kart(db, statement_balance=6576.90, min_payment_ratio=0.20)
    g = client.get(f"/api/accounts/{kart.id}").json()
    assert float(g["statement_balance"]) == 6576.90
    assert g["min_payment_ratio"] == 0.20


def test_ekstre_SIFIR_gecerlidir_None_a_cevrilmez(client, db):
    """0 = 'ekstre kapandı', None = 'bilinmiyor'. İkisi farklı sonuç üretir."""
    kart = _kart(db, statement_balance=6576.90)
    r = client.put(f"/api/accounts/{kart.id}", json={"statement_balance": 0})
    assert r.status_code == 200, r.text
    db.refresh(kart)
    assert kart.statement_balance is not None
    assert float(kart.statement_balance) == 0.0


@pytest.mark.parametrize("bozuk", [20, 1.5, -0.1, 100])
def test_oran_0_1_araligi_disinda_REDDEDILIR(client, db, bozuk):
    """%20'yi 0.20 yerine 20 yazmak asgariyi 100 kat büyütür — sessizce kabul edilemez."""
    kart = _kart(db)
    r = client.put(f"/api/accounts/{kart.id}", json={"min_payment_ratio": bozuk})
    assert r.status_code == 422, f"{bozuk} kabul edildi (beklenen 422)"
    db.refresh(kart)
    assert kart.min_payment_ratio is None
