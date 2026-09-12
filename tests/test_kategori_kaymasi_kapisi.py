"""
FEAT-033 / BUG #430 KAPISI — AY KARŞILAŞTIRMASINDA KATEGORİ KAYMALARI VE ANLATI.

Ölçülen (12 Eyl 2026): aylık özet gider TOPLAMININ yüzde trendini veriyordu; "gider neden
arttı?" sorusu kategoriye inmiyordu. `kategori_kaymalari` iki ayın gider kategorilerini
|fark|a göre sıralar; `ay_anlatisi` sayılardan tek paragraf üretir (model yok, deterministik).

Kilitlenen: durumlar (yeni/kayboldu/artti/azaldi); eşik altı gürültü listeye girmez; yeni
kategoriye yüzde uydurulmaz (None); sıralama |fark| desc; tavan; anlatı kısmi ayı açıkça
söyler; iki ayda gider yoksa anlatı None; uç anahtarları taşır ve `today` kısmi bilgisini
geçirir.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Account, AccountType, Base, Transaction, TransactionType, User
from app.rules_engine import (KAYMA_LISTE_TAVANI, ay_anlatisi, generate_monthly_summary,
                              kategori_kaymalari)


def _k(ad, toplam):
    return {"category": ad, "total": Decimal(str(toplam)), "count": 1}


def test_durumlar_ve_siralama_ve_esik():
    cur = [_k("market", 1500), _k("ulasim", 200), _k("saglik", 300), _k("kira", 10000), _k("kahve", 100.5)]
    prev = [_k("market", 1000), _k("ulasim", 500), _k("eglence", 400), _k("kira", 10000), _k("kahve", 100)]
    r = kategori_kaymalari(cur, prev)
    assert [k["category"] for k in r] == ["market", "eglence", "saglik", "ulasim"], "|fark| desc; kira (0) ve kahve (0,5 < eşik) yok"
    d = {k["category"]: k for k in r}
    assert d["market"]["durum"] == "artti" and d["market"]["delta"] == 500 and d["market"]["delta_pct"] == 50.0
    assert d["ulasim"]["durum"] == "azaldi" and d["ulasim"]["delta"] == -300 and d["ulasim"]["delta_pct"] == -60.0
    assert d["saglik"]["durum"] == "yeni" and d["saglik"]["delta_pct"] is None, "geçen ay 0 → yüzde uydurulmaz"
    assert d["eglence"]["durum"] == "kayboldu" and d["eglence"]["delta"] == -400


def test_tavan():
    cur = [_k(f"k{i}", 100 * (i + 1)) for i in range(KAYMA_LISTE_TAVANI + 3)]
    assert len(kategori_kaymalari(cur, [])) == KAYMA_LISTE_TAVANI


def test_anlati_tam_ay():
    cur = {"total_expense": Decimal("2000")}
    prev = {"total_expense": Decimal("1600")}
    kaymalar = kategori_kaymalari([_k("market", 1500), _k("saglik", 300), _k("ulasim", 200)],
                                  [_k("market", 1000), _k("ulasim", 600)])
    m = ay_anlatisi(cur, prev, kaymalar, "Ağustos")
    assert m.startswith("Gider Ağustos ayına göre %25 arttı")
    assert "en çok artan market (+" in m and "en çok azalan ulasim (−" in m and "yeni: saglik" in m
    assert "kısmi" not in m and m.endswith(".")


def test_anlati_kismi_ay_acikca_soyler():
    m = ay_anlatisi({"total_expense": Decimal("500")}, {"total_expense": Decimal("1000")}, [], "Ağustos",
                    kismi=True, today=date(2026, 9, 12))
    assert m.startswith("Ayın ilk 12 günü (Ağustos tam ayıyla kıyas, kısmi); gider Ağustos ayına göre %50 azaldı")


def test_anlati_kenarlari():
    z = Decimal("0")
    assert ay_anlatisi({"total_expense": z}, {"total_expense": z}, [], "Ağustos") is None
    assert ay_anlatisi({"total_expense": Decimal("10")}, {"total_expense": z}, [], "Ağustos") == "Ağustos ayında gider kaydı yoktu."
    assert ay_anlatisi({"total_expense": z}, {"total_expense": Decimal("10")}, [], "Ağustos") == "Bu ay henüz gider kaydı yok."
    assert ay_anlatisi({"total_expense": Decimal("10")}, {"total_expense": Decimal("10")}, [], "Ağustos") == "Gider Ağustos ayıyla aynı."


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)(); ses.add(User(id=1, name="u")); ses.commit()
    acc = Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=0); ses.add(acc); ses.commit()
    def tx(d, kat, tutar):
        ses.add(Transaction(user_id=1, account_id=acc.id, transaction_type=TransactionType.expense,
                            amount=tutar, transaction_date=d, category=kat))
    tx(date(2026, 9, 3), "market", 1500); tx(date(2026, 9, 5), "saglik", 300)
    tx(date(2026, 8, 3), "market", 1000); tx(date(2026, 8, 9), "ulasim", 600)
    ses.commit()
    yield ses; ses.close()


def test_ozet_kaymalari_ve_anlatiyi_tasir(s):
    r = generate_monthly_summary(1, 2026, 9, s, today=date(2026, 9, 12))
    assert [k["category"] for k in r["kategori_kaymalari"]] == ["ulasim", "market", "saglik"]
    assert r["anlati"].startswith("Ayın ilk 12 günü")
    assert "kısmi" not in generate_monthly_summary(1, 2026, 9, s, today=date(2026, 10, 2))["anlati"]
    assert "kısmi" not in generate_monthly_summary(1, 2026, 9, s)["anlati"]


def test_uc_today_gecirir(s, monkeypatch):
    import app.routers.reports as rp
    monkeypatch.setattr(rp, "user_today", lambda u: date(2026, 9, 12))
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        r = TestClient(app).get("/api/reports/monthly-summary")
        assert r.status_code == 200
        g = r.json()
        assert g["anlati"].startswith("Ayın ilk 12 günü"), g["anlati"]
        assert g["kategori_kaymalari"][0]["category"] == "ulasim"
    finally:
        app.dependency_overrides.clear()
