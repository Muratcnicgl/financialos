"""
FEAT-034 — otomatik kategori önerisi testi.

suggest_category() açıklama/işyeri metninden deterministik kategori türetir.
Kullanıcının açık kategori seçimini asla ezmemeli (bu davranış create_transaction
seviyesinde; burada saf fonksiyonu doğruluyoruz).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Account, AccountType
from app.routers.transactions import suggest_category


def _eq(got, expected, label):
    assert got == expected, f"{label}: beklenen {expected!r}, gelen {got!r}"
    print(f"  OK  {label}: {got!r}")


def test_marka_eslesir():
    print("test_marka_eslesir:")
    _eq(suggest_category("Migros alışveriş"), "alisveris", "migros")
    _eq(suggest_category("BIM"), "alisveris", "bim")
    _eq(suggest_category("Yemeksepeti akşam yemeği"), "yemek", "yemeksepeti")
    _eq(suggest_category("Opet benzin"), "ulasim", "opet")
    _eq(suggest_category("Netflix abonelik"), "eglence", "netflix")
    _eq(suggest_category("Turkcell fatura"), "fatura", "turkcell")
    _eq(suggest_category("Eczane ilaç"), "saglik", "eczane")


def test_genel_anahtar_kelime():
    print("test_genel_anahtar_kelime:")
    _eq(suggest_category("taksi ile geldim"), "ulasim", "taksi")
    _eq(suggest_category("kahve içtim"), "yemek", "kahve")
    _eq(suggest_category("sinema bileti"), "eglence", "sinema")


def test_eslesme_yok_none():
    print("test_eslesme_yok_none:")
    _eq(suggest_category("blabla xyz"), None, "eşleşmeyen metin")
    _eq(suggest_category(""), None, "boş")
    _eq(suggest_category(None), None, "None")


def test_buyuk_kucuk_harf_duyarsiz():
    print("test_buyuk_kucuk_harf_duyarsiz:")
    _eq(suggest_category("MIGROS"), "alisveris", "büyük harf")
    _eq(suggest_category("  Migros  "), "alisveris", "boşluklu")


def test_kelime_sinirinda_partial_eslesme():
    """Tek kelime anahtarlar token bazlı — substring yanlış pozitifi olmamalı."""
    print("test_kelime_sinirinda_partial_eslesme:")
    # 'sok' düz substring olsaydı 'sokak' → alisveris olurdu; token eşleşmesi engeller.
    _eq(suggest_category("sokak ortasında"), None, "sok, sokak'ta eşleşmez")
    _eq(suggest_category("kimbilir nereye"), None, "bim, kimbilir'de eşleşmez")
    # ama gerçek token eşleşir:
    _eq(suggest_category("sok markete gittim"), "alisveris", "sok gerçek token")


def test_kullanici_kategorisi_ezilmez_akis():
    """suggest_category saf fonksiyon; create_transaction yalnız kategori BOŞSA çağırır.
    Burada fonksiyonun boş-olmayan girdide de deterministik olduğunu doğruluyoruz —
    ezme mantığı endpoint seviyesinde (test_transaction_account_guard kapsıyor)."""
    print("test_kullanici_kategorisi_ezilmez_akis:")
    # çok kelimeli marka
    _eq(suggest_category("Turk Telekom internet faturası"), "fatura", "turk telekom")


# ============================================================
# ENDPOINT ENTEGRASYONU — create_transaction otomatik kategori doldurur
# ============================================================

@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(id=1, user_id=1, name="Nakit", account_type=AccountType.cash, balance=5000))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_endpoint_bos_kategori_aciklamadan_doldurulur(client):
    """Kategori boş + açıklama 'Migros...' → kategori 'alisveris' otomatik atanır (FEAT-034)."""
    r = client.post("/api/transactions", json={
        "transaction_type": "expense", "amount": 240, "account_id": 1,
        "description": "Migros haftalık alışveriş",
    })
    assert r.status_code == 201, r.text
    assert r.json()["category"] == "alisveris"


def test_endpoint_acik_kategori_ezilmez(client):
    """Kullanıcı kategori verdiyse çıkarım ONU EZMEZ."""
    r = client.post("/api/transactions", json={
        "transaction_type": "expense", "amount": 240, "account_id": 1,
        "category": "hediye", "description": "Migros'tan aldım ama hediye",
    })
    assert r.status_code == 201, r.text
    assert r.json()["category"] == "hediye"


def test_endpoint_gelir_kategorilenmez(client):
    """Gelir işlemlerinde çıkarım yapılmaz (yalnız gider)."""
    r = client.post("/api/transactions", json={
        "transaction_type": "income", "amount": 1000, "account_id": 1,
        "description": "Migros iadesi",
    })
    assert r.status_code == 201, r.text
    assert r.json()["category"] is None


if __name__ == "__main__":
    test_marka_eslesir()
    test_genel_anahtar_kelime()
    test_eslesme_yok_none()
    test_buyuk_kucuk_harf_duyarsiz()
    test_kelime_sinirinda_partial_eslesme()
    test_kullanici_kategorisi_ezilmez_akis()
    print("\nTUM TESTLER GECTI (FEAT-034)")
