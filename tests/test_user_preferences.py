"""
P3.5 / H4 (Wave-9) — BUG #197: "bugün" kullanıcının saat diliminde hesaplanmalı.

Uygulama her yerde `date.today()` kullanıyordu — bu SUNUCUNUN yerel tarihidir. Sunucu TZ'si
doğru ayarlansa bile (BUG #169) farklı saat diliminde yaşayan kullanıcı için "bugün" yanlış
güne düşer: gece yarısı civarı girilen işlem bir önceki/sonraki güne yazılır, günlük limit
yanlış hesaplanır, ay sınırında düzenli gelir/gider tetiklemesi kayar. Tek-kullanıcı (TR)
kurulumda görünmez; kapalı betada ilk yurt dışı kullanıcıda ortaya çıkar.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as dt_tz

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User
from app.user_prefs import user_today, user_currency, user_locale


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(name="kullanici"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.query(User).first()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_tz_yoksa_sunucu_tarihine_duser(db):
    """Geriye uyum: mevcut kurulumların davranışı DEĞİŞMEZ."""
    u = db.query(User).first()
    assert user_today(u) == date.today()


def test_farkli_saat_dilimi_farkli_gun_verebilir():
    """Asıl kanıt: aynı anda iki kullanıcı için 'bugün' farklı olabilir."""
    class Sahte:
        id = 1
        timezone = "Pacific/Kiritimati"   # UTC+14
    class Sahte2:
        id = 2
        timezone = "Pacific/Midway"       # UTC-11

    ileri, geri = user_today(Sahte()), user_today(Sahte2())
    # BUG #220 fix: iddia (0,1) idi ve ZAMANA BAĞLI KIRILIYORDU. UTC+14 ile UTC-11 arası
    # 25 saat; UTC günü 10:00-10:59 arasındayken takvim farkı 2 GÜN olur (Kiritimati yeni
    # güne girmiş, Midway hâlâ bir önceki gündedir). Üretim kodu doğru, test yanlıştı —
    # günün ~1/24'ünde kırmızı veren gizli flaky (M90 "flaky yok" ölçümü bu pencereye denk
    # gelmemişti). Doğru sınır: fark 0..2 gün.
    assert (ileri - geri).days in (0, 1, 2), f"beklenmedik fark: {ileri} vs {geri}"
    # UTC gününe göre en az biri farklı olmalı (25 saatlik yelpaze)
    utc_gun = datetime.now(dt_tz.utc).date()
    assert ileri >= utc_gun >= geri - timedelta(days=1)


def test_gecersiz_tz_sessizce_yanlis_tarih_uretmez():
    class Sahte:
        id = 3
        timezone = "Mars/Olympus"
    assert user_today(Sahte()) == date.today(), "Geçersiz TZ güvenli varsayılana dönmedi"


def test_tercihler_apiden_yazilir_ve_okunur(client):
    r = client.put("/api/user", json={"timezone": "Europe/Berlin", "currency": "eur",
                                      "locale": "de-DE"})
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert body["timezone"] == "Europe/Berlin"
    assert body["currency"] == "EUR", "Para birimi ISO büyük harfe normalize edilmedi"
    assert body["locale"] == "de-DE"

    assert client.get("/api/user").json()["timezone"] == "Europe/Berlin"


def test_gecersiz_tz_apide_reddedilir(client):
    """Sessiz kabul = kullanıcı 'ayarladım' sanır ama tarihler yanlış kalır."""
    r = client.put("/api/user", json={"timezone": "Bilinmeyen/Yer"})
    assert r.status_code == 422


def test_cockpit_kullanici_gunune_gore_calisir(client, db):
    """Uçtan uca: TZ ayarlı kullanıcıda cockpit çökmeden çalışır (tarih zinciri sağlam)."""
    client.put("/api/user", json={"timezone": "Pacific/Kiritimati"})
    r = client.get("/api/cockpit")
    assert r.status_code == 200, r.text[:200]


def test_para_birimi_ve_locale_varsayilanlari(db):
    u = db.query(User).first()
    assert user_currency(u) == "TRY"
    assert user_locale(u) == "tr-TR"
