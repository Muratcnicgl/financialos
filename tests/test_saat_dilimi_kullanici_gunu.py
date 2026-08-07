"""
D17 / BUG #237 — "bugün" kullanıcının saat diliminde olmalı: KULLANICI-BAĞLAMLI TÜM yollar.

ADR-042 "tarih üreten TÜM kullanıcı-bağlamlı yollar user_today kullanır" diyordu; disk bunu
çürüttü — yalnız 7 router benimsemişti. En ağırı: koç bir işlemi kaydederken
`action_executor` SUNUCU gününü yazıyordu → farklı saat dilimindeki kullanıcının kendi
girdiği veri KALICI olarak yanlış güne düşüyor (ay sınırında aylık özet/bütçe/limit de kayar).

TESTİN AYIRT EDİCİLİĞİ (mutasyona dayanıklılık): her senaryo UTC+14 (Pacific/Kiritimati) ve
UTC-11 (Pacific/Midway) uçlarında ayrı ayrı koşar. Bu iki bölgenin arasında 25 saat vardır,
yani HER AN en az biri sunucunun gününden farklıdır (ilk test bunu ispatlar). Dolayısıyla
`date.today()` kullanan bir uygulama bu dosyada — günün hangi saati olursa olsun —
en az bir parametrede DÜŞER.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, Transaction, TransactionType,
    PersonalDebt, DebtDirection, NetWorthSnapshot,
)
from app.user_prefs import user_today
from app.action_executor import propose_action, execute_pending_action

# UTC+14 ve UTC-11: aralarında 25 saat → her an günleri farklı.
TZ_UCLARI = ["Pacific/Kiritimati", "Pacific/Midway"]


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _kullanici(db, tz: str) -> User:
    u = User(name="beta kullanicisi", timezone=tz)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _nakit(db, user: User) -> Account:
    acc = Account(user_id=user.id, name="Vadesiz", account_type=AccountType.cash,
                  balance=10000.0)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _giris(user: User):
    app.dependency_overrides[get_current_user] = lambda: user


# ============================================================
# 0. Testin ayırt ediciliği (premis kanıtı)
# ============================================================

def test_iki_uc_saat_dilimi_her_an_farkli_gun_gosterir():
    """
    Bu dosyadaki her senaryonun ayırt edici olmasının şartı: UTC+14 ile UTC-11 aynı anda
    farklı günlerdedir, dolayısıyla en az biri sunucunun gününden farklıdır. Bu test
    düşerse aşağıdaki testler 'sunucu tarihi' hatasını kaçırabilir demektir.
    """
    class _K:
        id = 1
        timezone = TZ_UCLARI[0]

    class _M:
        id = 2
        timezone = TZ_UCLARI[1]

    dogu, bati = user_today(_K()), user_today(_M())
    assert dogu != bati, "iki uç saat dilimi aynı günü gösteriyor — test ayırt edici değil"
    assert date.today() in (dogu, bati) or dogu > date.today() > bati
    assert sum(1 for g in (dogu, bati) if g != date.today()) >= 1


# ============================================================
# 1. EN AĞIRI — koçun yazdığı işlem KALICI olarak yanlış güne düşüyordu
# ============================================================

@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_kocun_kaydettigi_islem_kullanicinin_gunune_yazilir(db, tz):
    u = _kullanici(db, tz)
    acc = _nakit(db, u)

    # Koçun tipik yolu: "bugün 300 TL market harcadım" → payload'da transaction_date YOK
    # (V3_GOD_MODE_PROMPT bilerek eklememesini söylüyor → default dalı çalışır).
    pending = propose_action(
        db=db, user_id=u.id, action_type="add_transaction",
        payload={"transaction_type": "expense", "amount": 300.0,
                 "category": "market", "account_id": acc.id},
        summary="300 TL market gideri",
    )
    db.commit()

    sonuc = execute_pending_action(db, pending.id, u.id)
    assert sonuc["success"], sonuc

    txn = db.query(Transaction).filter(Transaction.user_id == u.id).one()
    assert txn.transaction_date == user_today(u), (
        f"işlem {txn.transaction_date} gününe yazıldı, kullanıcının günü {user_today(u)} "
        f"(sunucu {date.today()})"
    )


@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_borc_odendi_isareti_kullanicinin_gunune_yazilir(db, tz):
    u = _kullanici(db, tz)
    _nakit(db, u)
    borc = PersonalDebt(user_id=u.id, counterparty="komsu",
                        direction=DebtDirection.payable, amount=500.0)
    db.add(borc)
    db.commit()
    db.refresh(borc)

    pending = propose_action(
        db=db, user_id=u.id, action_type="mark_debt_paid",
        payload={"debt_id": borc.id},
        summary="borç ödendi",
    )
    db.commit()

    sonuc = execute_pending_action(db, pending.id, u.id)
    assert sonuc["success"], sonuc

    db.refresh(borc)
    assert borc.paid_date == user_today(u)


@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_acik_verilen_tarih_korunur(db, tz):
    """Geriye uyum: payload tarih taşıyorsa saat dilimi onu EZMEZ."""
    u = _kullanici(db, tz)
    acc = _nakit(db, u)
    istenen = date(2026, 3, 14)

    pending = propose_action(
        db=db, user_id=u.id, action_type="add_transaction",
        payload={"transaction_type": "expense", "amount": 50.0,
                 "account_id": acc.id, "transaction_date": istenen.isoformat()},
        summary="50 TL geçmiş tarihli gider",   # BUG #266: özet tutarı söylemeli
    )
    db.commit()
    assert execute_pending_action(db, pending.id, u.id)["success"]

    txn = db.query(Transaction).filter(Transaction.user_id == u.id).one()
    assert txn.transaction_date == istenen


def test_saat_dilimi_tanimsizsa_davranis_degismez(db):
    """Geriye uyum kapısı: mevcut (TR, timezone=NULL) kurulumda sunucu günü korunur."""
    u = User(name="tz'siz kullanici")
    db.add(u)
    db.commit()
    db.refresh(u)
    acc = _nakit(db, u)

    pending = propose_action(
        db=db, user_id=u.id, action_type="add_transaction",
        payload={"transaction_type": "income", "amount": 100.0, "account_id": acc.id},
        summary="100 TL gelir",   # BUG #266: özet tutarı söylemeli
    )
    db.commit()
    assert execute_pending_action(db, pending.id, u.id)["success"]

    txn = db.query(Transaction).filter(Transaction.user_id == u.id).one()
    assert txn.transaction_date == date.today()


# ============================================================
# 2. Raporlar — kullanıcı yanlış sayıya bakarak PARA KARARI veriyor
# ============================================================

@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_aylik_ozet_parametresiz_kullanicinin_ayini_acar(db, client, tz):
    u = _kullanici(db, tz)
    _giris(u)

    r = client.get("/api/reports/monthly-summary")
    assert r.status_code == 200
    period = r.json()["period"]
    bugun = user_today(u)
    assert (period["year"], period["month"]) == (bugun.year, bugun.month)


@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_yaklasan_nakit_akisi_kullanicinin_gununden_baslar(db, client, tz):
    u = _kullanici(db, tz)
    _giris(u)
    bugun = user_today(u)

    # Ufkun tam sınırındaki alacak İÇERİDE, bir gün ötesi DIŞARIDA olmalı.
    db.add(PersonalDebt(user_id=u.id, counterparty="sinirdaki",
                        direction=DebtDirection.receivable, amount=100.0,
                        due_date=bugun + timedelta(days=30)))
    db.add(PersonalDebt(user_id=u.id, counterparty="ufkun otesi",
                        direction=DebtDirection.receivable, amount=100.0,
                        due_date=bugun + timedelta(days=31)))
    db.commit()

    r = client.get("/api/reports/upcoming-cashflow?days=30")
    assert r.status_code == 200
    veri = r.json()
    assert veri["today"] == bugun.isoformat()
    etiketler = {i["label"] for i in veri["items"]}
    assert "sinirdaki" in etiketler
    assert "ufkun otesi" not in etiketler


@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_net_deger_gecmisi_penceresi_kullanicinin_gununden_olculur(db, client, tz):
    u = _kullanici(db, tz)
    _giris(u)
    bugun = user_today(u)

    for gun, net in ((bugun - timedelta(days=30), 111.0),      # pencerenin tam sınırı → İÇERİDE
                     (bugun - timedelta(days=31), 222.0)):     # bir gün eskisi → DIŞARIDA
        db.add(NetWorthSnapshot(user_id=u.id, snapshot_date=gun, net_worth_seen=net,
                                net_worth_full=net, cash=net, card_debt=0.0,
                                loan_debt=0.0, investment_value=0.0, receivables=0.0))
    db.commit()

    r = client.get("/api/reports/net-worth-trend?days=30")
    assert r.status_code == 200
    tarihler = {i["date"] for i in r.json()["items"]}
    assert (bugun - timedelta(days=30)).isoformat() in tarihler
    assert (bugun - timedelta(days=31)).isoformat() not in tarihler


@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_kategori_dagilimi_penceresi_kullanicinin_gununden_olculur(db, client, tz):
    u = _kullanici(db, tz)
    acc = _nakit(db, u)
    _giris(u)
    bugun = user_today(u)

    db.add(Transaction(user_id=u.id, account_id=acc.id,
                       transaction_type=TransactionType.expense, amount=100.0,
                       category="sinirdaki", transaction_date=bugun - timedelta(days=30)))
    db.add(Transaction(user_id=u.id, account_id=acc.id,
                       transaction_type=TransactionType.expense, amount=100.0,
                       category="pencere disi", transaction_date=bugun - timedelta(days=31)))
    db.commit()

    r = client.get("/api/reports/category-breakdown?days=30&type=expense")
    assert r.status_code == 200
    kategoriler = {i["category"] for i in r.json()["items"]}
    assert "sinirdaki" in kategoriler
    assert "pencere disi" not in kategoriler


@pytest.mark.parametrize("uc,hedef", [
    ("net-worth-attribution", "calculate_networth_attribution"),
    ("real-net-worth", "calculate_real_networth"),
])
@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_net_deger_hesaplarina_kullanicinin_gunu_gecilir(db, client, tz, uc, hedef, monkeypatch):
    """Bu iki uç hesabı rules_engine'e delege eder — geçilen 'bugün' kullanıcınınki olmalı."""
    from app.routers import reports as reports_router

    gorulen = {}

    def _yakala(user_id, bugun, _db):
        gorulen["tarih"] = bugun
        return None

    monkeypatch.setattr(reports_router, hedef, _yakala)

    u = _kullanici(db, tz)
    _giris(u)
    assert client.get(f"/api/reports/{uc}").status_code == 200
    assert gorulen["tarih"] == user_today(u)


# ============================================================
# 3. Abonelik tespiti + cockpit snapshot + koç bağlamı
# ============================================================

@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_abonelik_tespiti_kullanicinin_gununu_kullanir(db, client, tz, monkeypatch):
    from app.routers import subscriptions as subs_router

    gorulen = {}

    def _yakala(user_id, bugun, _db, lookback_days=180):
        gorulen["tarih"] = bugun
        return {"abonelikler": [], "aylik_toplam": 0.0, "yillik_toplam": 0.0, "adet": 0}

    monkeypatch.setattr(subs_router, "detect_subscriptions", _yakala)

    u = _kullanici(db, tz)
    _giris(u)
    assert client.get("/api/subscriptions").status_code == 200
    assert gorulen["tarih"] == user_today(u)


@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_net_deger_snapshotu_kullanicinin_gunuyle_damgalanir(db, client, tz):
    """
    Aynı istek içinde cockpit kullanıcının gününü, snapshot sunucununkini kullanıyordu —
    trend grafiği kullanıcının gördüğü günle hizasızdı (kendi içinde tutarsız istek).
    """
    u = _kullanici(db, tz)
    _nakit(db, u)
    _giris(u)

    assert client.get("/api/cockpit").status_code == 200

    snaplar = db.query(NetWorthSnapshot).filter(NetWorthSnapshot.user_id == u.id).all()
    assert len(snaplar) == 1
    assert snaplar[0].snapshot_date == user_today(u)


@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_koc_baglami_kullanicinin_gunuyle_uretilir(db, tz, monkeypatch):
    """Koçun gördüğü cockpit yanlış günden üretilirse verdiği tavsiye de yanlış güne aittir."""
    import app.coach as coach_mod

    gorulen = {}
    gercek = coach_mod.generate_cockpit

    def _yakala(user_id, bugun, _db):
        gorulen["tarih"] = bugun
        return gercek(user_id, bugun, _db)

    monkeypatch.setattr(coach_mod, "generate_cockpit", _yakala)

    u = _kullanici(db, tz)
    _nakit(db, u)
    coach_mod._build_context_message(db, u.id)
    assert gorulen["tarih"] == user_today(u)


@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_premortem_snapshotu_kullanicinin_gunuyle_uretilir(db, tz, monkeypatch):
    import app.cockpit_snapshot as snap_mod

    gorulen = {}
    gercek = snap_mod.generate_cockpit

    def _yakala(user_id, bugun, _db):
        gorulen["tarih"] = bugun
        return gercek(user_id, bugun, _db)

    monkeypatch.setattr(snap_mod, "generate_cockpit", _yakala)

    u = _kullanici(db, tz)
    _nakit(db, u)
    snap_mod.build_cockpit_snapshot(db, u.id)
    assert gorulen["tarih"] == user_today(u)


# ============================================================
# 4. Nakit akışı projeksiyonu + simülasyon + hedef motoru
# ============================================================

@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_nakit_akisi_projeksiyonu_kullanicinin_gununden_baslar(db, tz):
    from app.cashflow import generate_forecast

    u = _kullanici(db, tz)
    _nakit(db, u)
    sonuc = generate_forecast(db, u.id, horizon_days=30)
    assert sonuc["start_date"] == user_today(u).isoformat()


@pytest.mark.parametrize("tz", TZ_UCLARI)
def test_simulasyon_kullanicinin_gununden_baslar(db, tz, monkeypatch):
    import app.simulation_engine as sim_mod

    gorulen = {}
    gercek = sim_mod._load_world

    def _yakala(_db, user_id, bugun):
        gorulen.setdefault("tarih", bugun)
        return gercek(_db, user_id, bugun)

    monkeypatch.setattr(sim_mod, "_load_world", _yakala)

    u = _kullanici(db, tz)
    acc = _nakit(db, u)
    sim_mod.simulate_action(
        db=db, user_id=u.id, action_type="add_transaction",
        payload={"transaction_type": "expense", "amount": 100.0, "account_id": acc.id},
        horizons_days=[30],
    )
    assert gorulen["tarih"] == user_today(u)
