"""
BUG #256 (H4) — kullanıcı tercihi ↔ biçimlendirme ↔ API zinciri tek kaynakta mı.

ÖNCESİ: `User.currency` alanı vardı, API onu yazıyordu, `user_prefs.user_currency()` onu
okuyordu — ama **hiçbir üretim kodu o fonksiyonu çağırmıyordu** (yalnız testler). Yani
kullanıcının "para birimim" tercihi ölü bir alandı; arayüz her koşulda "TL" yazıyordu.
Bu, ADR-042'nin "alan olarak şimdi, görüntüleme sonra" kararının bıraktığı boşluktu ve
BUG #251'in ("ayarlanabilir görünüp gösterilememesi") asıl sebebiydi.

Burada üç halkanın tek kaynağa bağlı olduğu kilitlenir:
  API'nin kabul ettiği kodlar  ==  biçimlendiricinin desteklediği kodlar
  user_prefs.user_currency     ->  money_format.kullanici_para_kodu (tek uygulama)
  bozuk DB değeri              ->  çökme YOK, güvenli varsayılan (veri yolu fail-safe)
  desteklenmeyen kod (kod yolu) ->  fail-fast istisna
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User
from app.money_format import (
    DesteklenmeyenParaBirimi,
    desteklenen_kodlar,
    format_para,
    kullanici_para_kodu,
    para_etiketi,
)
from app.user_prefs import user_currency
from app.routers.user import DESTEKLENEN_PARA_BIRIMLERI


class _SahteKullanici:
    def __init__(self, currency=None, id=1):
        self.currency = currency
        self.id = id


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


def test_api_kumesi_bicimlendirici_kumesinden_turetilir():
    """L27: iki liste elle taşınırsa bir gün ayrışır — aynı kaynaktan gelmeli."""
    assert DESTEKLENEN_PARA_BIRIMLERI == set(desteklenen_kodlar())
    assert DESTEKLENEN_PARA_BIRIMLERI == {"TRY"}, (
        "TRY kilidi bilinçli bir üründür kararıdır (ADR-044); genişletmek kur çevrimi ADR'si ister"
    )


def test_user_prefs_tek_uygulamaya_devreder():
    kullanici = _SahteKullanici(currency="try")
    assert user_currency(kullanici) == kullanici_para_kodu(kullanici) == "TRY"


def test_tercih_yoksa_varsayilan():
    assert kullanici_para_kodu(_SahteKullanici(currency=None)) == "TRY"
    assert kullanici_para_kodu(None) == "TRY"
    assert para_etiketi(_SahteKullanici()) == "TL"


def test_veri_yolu_fail_safe_bozuk_kayit_cokertmez():
    """
    DB'de BUG #246 doğrulamasından ÖNCE yazılmış bir çöp değer olabilir. Kullanıcının
    kendi verisini açamaz hale gelmesi, yanlış etiketten ağır bir zarardır (L6).

    NOT (test izolasyonu): `caplog` kullanılmıyor — süitteki başka bir test logging
    yapılandırmasını değiştirdiğinde bu test TEK BAŞINA yeşil, süit içinde kırmızı
    oluyordu (sıra-bağımlı kırılganlık; BUG #220 sınıfı). Kendi handler'ını takarak
    global yapılandırmadan bağımsız ölçüyoruz.
    """
    import app.money_format as mf

    kayitlar: list[str] = []
    orijinal = mf.logger.warning
    mf.logger.warning = lambda msg, *a, **k: kayitlar.append(str(msg) % a if a else str(msg))
    try:
        bozuk = _SahteKullanici(currency="XYZ", id=7)
        assert kullanici_para_kodu(bozuk) == "TRY"
        assert any("XYZ" in m for m in kayitlar), \
            "bozuk para birimi SESSİZCE yutulmamalı — uyarı verilmeli"
        # ve biçimlendirme çalışmaya devam eder
        assert format_para(1234.56, bozuk) == "1.234,56 TL"
    finally:
        mf.logger.warning = orijinal


def test_kod_yolu_fail_fast():
    """Geliştirici hatası sessizce yanlış etiketli para üretmemeli."""
    with pytest.raises(DesteklenmeyenParaBirimi):
        format_para(100, kod="USD")


def test_api_ucu_desteklenmeyen_kodu_reddeder(client):
    """Uçtaki davranış: 422 + gerekçe (kullanıcı 'ayarladım' sanmasın)."""
    r = client.put("/api/user", json={"currency": "USD"})
    assert r.status_code == 422
    assert "TRY" in r.json()["detail"]

    r2 = client.put("/api/user", json={"currency": "try"})
    assert r2.status_code == 200
    assert r2.json()["currency"] == "TRY", "kod normalize edilmeli"
