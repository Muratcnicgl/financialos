"""
KULLANIM TURU DEĞİŞMEZLERİ — statik denetimin göremediği sınıf için kalıcı kapı.

Bu turda kapanan üç kullanıcı bildirimi (#232 pasif kural görünmüyordu, #233 Google
hesabına şifre belirlenemiyordu, #241 tahsilat nakde geçmiyordu) tek bir şeyi söylüyor:
**gerçek kullanım, statik denetimin bulamadığı defekt üretiyor.** Ortak yanları, tek tek
uçların DOĞRU olması ama bir DİZİ işlemin sonunda paranın tutmamasıydı.

Bu dosya "bir günlük kullanım"ı uçlar üzerinden koşturur ve HER adımdan sonra üç
değişmezi ölçer:

  D1. **Muhasebe kimliği:** cockpit'in gösterdiği Görülen Net Değer, hesap bakiyelerinden
      hesaplanana EŞİT olmalı (panel ile motor ayrışamaz).
  D2. **Beklenen delta:** her işlemin net değere etkisi ÖNCEDEN bilinir; ölçülen delta
      ondan sapamaz (gider −tutar, tahsilat 0, kart ödemesi 0 …).
  D3. **Hiçbir uç 500 vermez:** mutasyondan sonra kullanıcının açacağı her panel açılır
      (BUG #219 sınıfı: veri belirli bir hâle gelince panel çöküyordu).

Not: değişmezler ürün sözleşmesidir, uygulama ayrıntısı değil. Bir gün "tahsilat net-nötr
değil" denirse bu dosya bilinçli olarak güncellenir — sessizce kaymaz.
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
from app.models import Base, User, Account, AccountType

BUGUN = date(2026, 8, 6)

# Mutasyondan sonra kullanıcının gerçekten açtığı paneller (hepsi 200 dönmeli — D3)
PANEL_UCLARI = [
    "/api/cockpit", "/api/accounts", "/api/transactions", "/api/incomes",
    "/api/expenses/recurring", "/api/debts", "/api/checkpoints", "/api/goals",
    "/api/envelopes", "/api/wishlist", "/api/subscriptions", "/api/actions/pending",
    "/api/reports/monthly-summary", "/api/reports/category-breakdown",
    "/api/reports/net-worth-trend", "/api/cashflow/forecast",
    "/api/debt-strategy/compare", "/api/reports/upcoming-cashflow",
]


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="kullanici", email="k@example.com"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def hesaplar(db_session):
    nakit = Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=20000)
    kart = Account(user_id=1, name="Kart", account_type=AccountType.credit_card,
                   balance=5000, credit_limit=30000, statement_day=1, payment_day=10)
    db_session.add_all([nakit, kart])
    db_session.commit()
    db_session.refresh(nakit); db_session.refresh(kart)
    return {"nakit": nakit, "kart": kart}


# ============================================================
# YARDIMCILAR
# ============================================================

def _cockpit(client) -> dict:
    r = client.get("/api/cockpit")
    assert r.status_code == 200, f"cockpit {r.status_code}: {r.text[:200]}"
    return r.json()


def _hesaplardan_net(client) -> float:
    """Görülen Net Değer'i HESAPLARDAN hesapla (cockpit'ten bağımsız ikinci ölçüm)."""
    hesaplar = client.get("/api/accounts").json()
    nakit = sum(h["balance"] for h in hesaplar if h["account_type"] == "cash" and not h["is_emanet"])
    yatirim = sum(h["balance"] for h in hesaplar if h["account_type"] == "investment" and not h["is_emanet"])
    kart = sum(h["balance"] for h in hesaplar if h["account_type"] == "credit_card")
    kredi = sum(h["balance"] for h in hesaplar if h["account_type"] == "loan")
    return round(nakit + yatirim - kart - kredi, 2)


def _panelleri_ac(client) -> None:
    """D3: mutasyon sonrası hiçbir panel çökmemeli."""
    hatalar = []
    for uc in PANEL_UCLARI:
        r = client.get(uc)
        if r.status_code >= 500:
            hatalar.append(f"{uc} → {r.status_code}: {r.text[:120]}")
    assert not hatalar, "Mutasyondan sonra panel(ler) çöktü:\n" + "\n".join(hatalar)


def _adim(client, aciklama: str, islem, beklenen_delta: float) -> None:
    """İşlemi koştur; D1 (muhasebe kimliği) + D2 (beklenen delta) + D3 (panel) ölç."""
    once = _cockpit(client)["net_deger"]
    islem()
    sonra_cockpit = _cockpit(client)
    sonra = sonra_cockpit["net_deger"]

    assert sonra == pytest.approx(_hesaplardan_net(client), abs=0.01), (
        f"[{aciklama}] D1 KIRILDI: cockpit {sonra} ≠ hesaplardan {_hesaplardan_net(client)} "
        "— panel ile motor ayrışmış"
    )
    assert (sonra - once) == pytest.approx(beklenen_delta, abs=0.01), (
        f"[{aciklama}] D2 KIRILDI: net değer {once} → {sonra} "
        f"(delta {sonra - once:+.2f}, beklenen {beklenen_delta:+.2f})"
    )
    _panelleri_ac(client)


# ============================================================
# TUR
# ============================================================

def test_gunluk_kullanim_turu_para_tutar(client, hesaplar, db_session):
    """Bir günlük gerçek kullanım: gider, gelir, alacak-tahsili, borç, kart ödemesi."""
    nakit_id, kart_id = hesaplar["nakit"].id, hesaplar["kart"].id

    # 1) Nakit gider — net değer TUTAR KADAR düşer
    _adim(client, "nakit gider 300", lambda: client.post("/api/transactions", json={
        "transaction_type": "expense", "amount": 300, "category": "market",
        "account_id": nakit_id, "transaction_date": BUGUN.isoformat(),
    }), beklenen_delta=-300)

    # 2) Kart harcaması — kart borcu artar, net değer yine tutar kadar düşer
    _adim(client, "kart harcamasi 450", lambda: client.post("/api/transactions", json={
        "transaction_type": "expense", "amount": 450, "category": "yemek",
        "account_id": kart_id, "is_card_expense": True,
        "transaction_date": BUGUN.isoformat(),
    }), beklenen_delta=-450)

    # 3) Gelir — net değer tutar kadar artar
    _adim(client, "gelir 5000", lambda: client.post("/api/transactions", json={
        "transaction_type": "income", "amount": 5000, "category": "maas",
        "account_id": nakit_id, "transaction_date": BUGUN.isoformat(),
    }), beklenen_delta=+5000)

    # 4) Alacak kaydı — GÖRÜLEN net değeri DEĞİŞTİRMEZ (henüz tahsil edilmedi)
    alacak = {"counterparty": "Yakin kisi", "direction": "receivable", "amount": 2000,
              "due_date": (BUGUN + timedelta(days=3)).isoformat()}
    _adim(client, "alacak kaydi", lambda: client.post("/api/debts", json=alacak),
          beklenen_delta=0)
    alacak_id = client.get("/api/debts").json()[0]["id"]

    # 5) TAHSİLAT (BUG #241) — nakit artar, alacak düşer: GÖRÜLEN net +2000, TAM net sabit
    tam_once = _cockpit(client)["net_deger_tam"]
    _adim(client, "alacak tahsili", lambda: client.put(f"/api/debts/{alacak_id}",
                                                       json={"is_paid": True}),
          beklenen_delta=+2000)
    assert _cockpit(client)["net_deger_tam"] == pytest.approx(tam_once, abs=0.01), (
        "Tahsilat TAM net değeri değiştirdi — para buharlaştı/üretildi (BUG #241 sınıfı)"
    )

    # 6) Borç kaydı + ödemesi — ödeme GÖRÜLEN net değeri düşürür, TAM net sabit kalır
    client.post("/api/debts", json={"counterparty": "Komsu", "direction": "payable",
                                    "amount": 800})
    borc_id = [d for d in client.get("/api/debts").json() if d["direction"] == "payable"][0]["id"]
    tam_once = _cockpit(client)["net_deger_tam"]
    _adim(client, "borc odemesi", lambda: client.put(f"/api/debts/{borc_id}",
                                                     json={"is_paid": True}),
          beklenen_delta=-800)
    assert _cockpit(client)["net_deger_tam"] == pytest.approx(tam_once, abs=0.01)

    # 7) Kart ödemesi — nakit çıkar, kart borcu düşer: net değer DEĞİŞMEZ (transfer)
    db_session.expire_all()
    _adim(client, "kart odemesi 450", lambda: client.post("/api/transactions", json={
        "transaction_type": "income", "amount": 450, "category": "kart-odemesi",
        "account_id": kart_id, "transaction_date": BUGUN.isoformat(),
    }) and client.post("/api/transactions", json={
        "transaction_type": "expense", "amount": 450, "category": "kart-odemesi",
        "account_id": nakit_id, "transaction_date": BUGUN.isoformat(),
    }), beklenen_delta=0)


def test_geri_alma_turu_para_uretmez(client, hesaplar):
    """Kullanıcı yanlış işaretler, geri alır, tekrar işaretler — para üretilmemeli."""
    client.post("/api/debts", json={"counterparty": "Yakin kisi", "direction": "receivable",
                                    "amount": 1500})
    debt_id = client.get("/api/debts").json()[0]["id"]
    baslangic = _cockpit(client)["net_deger"]

    for _ in range(3):
        client.put(f"/api/debts/{debt_id}", json={"is_paid": True})
        client.put(f"/api/debts/{debt_id}", json={"is_paid": False})

    assert _cockpit(client)["net_deger"] == pytest.approx(baslangic, abs=0.01), (
        "İşaretle/geri al döngüsü net değeri kaydırdı — çift-sayım/hayalet para"
    )
    assert _cockpit(client)["net_deger"] == pytest.approx(_hesaplardan_net(client), abs=0.01)


def test_bos_kullanicida_hicbir_panel_cokmez(client):
    """Yeni kullanıcı (hiç veri yok) — en sık ilk-deneyim, en kolay unutulan hâl."""
    _panelleri_ac(client)
    c = _cockpit(client)
    assert c["net_deger"] == 0 and c["nakit_kasa"] == 0


def test_silme_sonrasi_muhasebe_kimligi_korunur(client, hesaplar):
    """Kayıt silme de bir kullanım adımıdır: sildikten sonra panel ile motor uyuşmalı."""
    client.post("/api/debts", json={"counterparty": "Yakin kisi", "direction": "receivable",
                                    "amount": 900})
    debt_id = client.get("/api/debts").json()[0]["id"]
    client.put(f"/api/debts/{debt_id}", json={"is_paid": True})
    once = _cockpit(client)["net_deger"]

    client.delete(f"/api/debts/{debt_id}")

    sonra = _cockpit(client)["net_deger"]
    assert sonra == pytest.approx(_hesaplardan_net(client), abs=0.01), (
        "Silme sonrası cockpit ile hesaplar ayrıştı"
    )
    assert sonra == pytest.approx(once - 900, abs=0.01), (
        "Silinen tahsilatın nakit etkisi geri sarılmadı (sahipsiz bakiye)"
    )
    _panelleri_ac(client)


def test_islem_duzenleme_ve_silme_turu(client, hesaplar):
    """Kullanıcı yanlış girer, düzeltir, siler — her adımda muhasebe kimliği korunmalı.

    Bu üç adım (tutar düzeltme / hesap taşıma / silme) BUG #241 ile aynı aileden:
    bir kaydın ETKİSİ kaydın kendisiyle senkron kalmalı."""
    nakit_id, kart_id = hesaplar["nakit"].id, hesaplar["kart"].id

    r = client.post("/api/transactions", json={
        "transaction_type": "expense", "amount": 300, "category": "market",
        "account_id": nakit_id, "transaction_date": BUGUN.isoformat()})
    assert r.status_code in (200, 201), r.text[:200]
    txn_id = r.json()["id"]

    # Tutar düzeltmesi: 300 → 500 (net değer 200 daha düşer)
    _adim(client, "tutar duzeltme 300->500",
          lambda: client.put(f"/api/transactions/{txn_id}", json={"amount": 500}),
          beklenen_delta=-200)

    # Hesap taşıma: nakit gideri KART giderine taşı — net değer AYNI kalır
    # (ikisi de varlığı 500 azaltır; biri nakdi düşürür, diğeri kart borcunu artırır)
    _adim(client, "hesap tasima nakit->kart",
          lambda: client.put(f"/api/transactions/{txn_id}", json={"account_id": kart_id}),
          beklenen_delta=0)

    # Silme: etki geri sarılır
    _adim(client, "islem silme",
          lambda: client.delete(f"/api/transactions/{txn_id}"),
          beklenen_delta=+500)


def test_yatirim_fiyati_turu(client, hesaplar, db_session):
    """Fiyat güncellemesi net değeri lot × fark kadar oynatmalı; panel/motor ayrışmamalı."""
    from app.models import Account, AccountType
    fon = Account(user_id=1, name="Fon", account_type=AccountType.investment,
                  balance=10000, fund_code="ABC", lot_count=10, cost_per_lot=1000,
                  current_price=1000)
    db_session.add(fon); db_session.commit(); db_session.refresh(fon)

    once = _cockpit(client)["net_deger"]
    r = client.put(f"/api/accounts/{fon.id}", json={"current_price": 1200})
    assert r.status_code == 200, r.text[:200]
    sonra = _cockpit(client)["net_deger"]

    assert sonra == pytest.approx(_hesaplardan_net(client), abs=0.01), (
        "Fiyat güncellemesi sonrası cockpit ile hesaplar ayrıştı"
    )
    assert sonra - once == pytest.approx(2000, abs=0.01), (
        f"10 lot × 200 TL artış net değere yansımadı (delta {sonra - once:+.2f})"
    )
    _panelleri_ac(client)
