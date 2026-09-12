"""
DVIZ-005 / BUG #429 KAPISI — KOKPİT KARTLARININ "AY BAŞINDAN BERİ" FARKI.

Ölçülen (12 Eyl 2026): `NetWorthSnapshot` geçmişi günlerdir birikiyordu ama kokpit
kartları yalnız mutlak değer taşıyordu; "kart borcu geçen aya göre düştü mü" sorusu
Raporlar'daki eğriden okunmak zorundaydı. `donem_degisimi` bugünün CANLI değeri ile
bugünden önceki bir snapshot arasındaki farkı verir.

Kilitlenen: baz yoksa None (sıfır değil, L45); baz ay başı snapshot'ı (7 gün tolerans),
yoksa bugünden önceki en eski; BUGÜNÜN snapshot'ı asla baz olmaz (ilk istek yazdıktan
sonra ikincisi "0 fark" göstermesin); fark = canlı − baz, alan alan; uç anahtarı taşır.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Base, NetWorthSnapshot, User
from app.routers.cockpit import AY_BASI_TOLERANSI_GUN, DEGISIM_ALANLARI, _donem_degisimi

BUGUN = date(2026, 9, 12)
CANLI = {"nakit_kasa": 300.0, "kart_borcu": 50.0, "kredi_borcu": 0.0, "yatirim_deger": 20.0,
         "net_deger": 270.0, "net_deger_tam": 290.0}


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)(); ses.add(User(id=1, name="u")); ses.commit()
    yield ses; ses.close()


def _snap(ses, gun, **degerler):
    v = dict(cash=100, card_debt=80, loan_debt=0, investment_value=10,
             net_worth_seen=30, net_worth_full=40, receivables=10)
    v.update(degerler)
    ses.add(NetWorthSnapshot(user_id=1, snapshot_date=gun, **v)); ses.commit()


def test_baz_yoksa_None(s):
    assert _donem_degisimi(s, 1, None, CANLI, BUGUN) is None


def test_ay_basi_snapshoti_baz_ve_fark_canli_eksi_baz(s):
    _snap(s, date(2026, 9, 1))
    _snap(s, date(2026, 9, 8), cash=999)   # aradaki gün baz DEĞİL
    r = _donem_degisimi(s, 1, None, CANLI, BUGUN)
    assert (r["baz_tarih"], r["gun"], r["ay_basi"]) == ("2026-09-01", 11, True)
    assert (r["nakit_kasa"], r["kart_borcu"], r["yatirim_deger"]) == (200.0, -30.0, 10.0)
    assert (r["net_deger"], r["net_deger_tam"]) == (240.0, 250.0)
    assert {k for k, _ in DEGISIM_ALANLARI} <= set(r)


def test_ay_basinda_snapshot_yoksa_toleransli_onceki_ay_sonu(s):
    _snap(s, date(2026, 9, 1) - timedelta(days=AY_BASI_TOLERANSI_GUN), cash=150)
    r = _donem_degisimi(s, 1, None, CANLI, BUGUN)
    assert (r["baz_tarih"], r["ay_basi"], r["nakit_kasa"]) == ("2026-08-25", True, 150.0)


def test_tolerans_disi_ise_en_eski_ve_ay_basi_degil(s):
    _snap(s, date(2026, 9, 1) - timedelta(days=AY_BASI_TOLERANSI_GUN + 1), cash=1)
    _snap(s, date(2026, 9, 5), cash=2)
    r = _donem_degisimi(s, 1, None, CANLI, BUGUN)
    assert (r["baz_tarih"], r["ay_basi"], r["gun"], r["nakit_kasa"]) == ("2026-08-24", False, 19, 299.0)


def test_bugunun_snapshoti_asla_baz_olmaz(s):
    """Ayın 1'inde ikinci istek: bugünün snapshot'ı yazılmış — ona göre '0 fark' basılmasın."""
    ilk = date(2026, 9, 1)
    _snap(s, ilk, cash=300)                      # bugün (canlıyla aynı → fark 0 olurdu)
    _snap(s, date(2026, 8, 31), cash=120)        # gerçek baz
    r = _donem_degisimi(s, 1, None, CANLI, ilk)
    assert (r["baz_tarih"], r["nakit_kasa"]) == ("2026-08-31", 180.0)
    s.query(NetWorthSnapshot).filter(NetWorthSnapshot.snapshot_date == date(2026, 8, 31)).delete()  # scope-exempt: test
    s.commit()
    assert _donem_degisimi(s, 1, None, CANLI, ilk) is None, "yalnız bugünün snapshot'ı varsa baz yok"


def test_workspace_bazi_ayri(s):
    _snap(s, date(2026, 9, 1), cash=100)
    s.add(NetWorthSnapshot(user_id=1, workspace_id=7, snapshot_date=date(2026, 8, 30), cash=5, card_debt=0,
                           loan_debt=0, investment_value=0, net_worth_seen=5, net_worth_full=5, receivables=0))
    s.commit()
    assert _donem_degisimi(s, 1, 7, CANLI, BUGUN)["nakit_kasa"] == 295.0
    assert _donem_degisimi(s, 1, None, CANLI, BUGUN)["nakit_kasa"] == 200.0


def test_uc_anahtari_tasir_bos_kullanicida_None(s):
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        r = TestClient(app).get("/api/cockpit")
        assert r.status_code == 200
        assert "donem_degisimi" in r.json() and r.json()["donem_degisimi"] is None
        # ilk istek bugünün snapshot'ını yazdı; ikinci istekte hâlâ baz yok (bugün baz olmaz)
        assert TestClient(app).get("/api/cockpit").json()["donem_degisimi"] is None
    finally:
        app.dependency_overrides.clear()
