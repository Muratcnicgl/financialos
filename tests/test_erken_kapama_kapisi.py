"""
BUG #318 KAPISI — BİR KREDİNİN İKİ SAYISI VARDIR VE KARIŞTIRILAMAZ.

ÖLÇÜLEN DEFEKT (2 Eyl 2026, altın senaryo G1): koça "Garanti'deki iki kredimi bugün tek
seferde kapatsam her biri için ne öderim?" soruldu. Koç **79.625,85 TL** dedi. Doğrusu
48.510,41 TL (14.023,29 + 34.487,12). Yani kullanıcıya **31.115,44 TL fazla ödeme**
tavsiye edildi.

Sebep bir prompt eksikliği DEĞİLDİ: cockpit'te "kapatma bedeli" diye bir SAYI yoktu.
`balance` kalan taksit toplamıdır (gelecek faizi içerir); kapama bedeli `notes` içinde
serbest METİN olarak duruyordu. Model, elindeki tek sayıyı kullandı.

İkinci ve daha sinsi zarar: koç `notes`u okuyup DOĞRU tutarı söylese bile, grounding o
sayıyı cockpit'in sayısal yapraklarında bulamayacağı için "izlenemeyen tutar" damgası
basardı. **Ürün, doğru cevabı cezalandıracak biçimde kuruluydu.**

BU KAPININ TUTTUĞU SÖZLEŞME:
  1. Alan SAYISALDIR ve uçtan uca taşınır (DB → cockpit → koç bağlamı → API).
  2. İki sayı BİRBİRİNİN YERİNE GEÇMEZ; koç bağlamı bunu açıkça söyler.
  3. BİLİNMİYORSA SIFIR DEĞİLDİR (L45): alan boşken koç "bilmiyorum, sor" der —
     0 TL yazmak "borcun yok" demek olurdu.
  4. Tutar İKİ YERDE tutulmaz: `notes`a geri sızarsa biri bayatlar.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Account, AccountType, Base, User
from app.rules_engine import calculate_getiri_esigi, generate_cockpit

KAPAMA = 14023.29
BAKIYE = 16439.65


def _db(kapama=KAPAMA, notes=None):
    # TestClient uygulamayi AYRI bir thread'de kosar; in-memory SQLite baglantisi ise
    # yaratildigi thread'e baglidir. StaticPool tek baglantiyi paylastirir.
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="T"))
    s.add(Account(user_id=1, name="Nakit", account_type=AccountType.cash, balance=1000.0))
    s.add(Account(user_id=1, name="Kredi", account_type=AccountType.loan,
                  balance=BAKIYE, monthly_payment=4109.90, remaining_installments=4,
                  interest_rate=4.75, early_payoff_amount=kapama, notes=notes))
    s.commit()
    return s


def _kredi_detayi(cockpit):
    return next(a for a in cockpit["accounts"] if a["tip"] == "loan")


@pytest.fixture
def istemci():
    """Projedeki yerleşik desen: bağımlılıklar izole in-memory oturuma bağlanır."""
    db = _db()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        db.close()


# ---- 1) ALAN SAYISAL VE UÇTAN UCA TAŞINIYOR -----------------------------------

def test_alan_modelde_sayisal():
    """Serbest metin bir veri modeli değildir: alan Numeric olmalı."""
    kolon = Account.__table__.c["early_payoff_amount"]
    assert str(kolon.type).startswith("NUMERIC"), f"tip {kolon.type} — sayısal değil"
    assert kolon.nullable, "NULL = bilinmiyor; zorunlu yapmak uydurmaya zorlar"


def test_cockpite_ayri_alan_olarak_giriyor():
    db = _db()
    try:
        c = generate_cockpit(1, date(2026, 9, 2), db)
    finally:
        db.close()
    kredi = _kredi_detayi(c)
    assert float(kredi["erken_kapama"]) == KAPAMA
    # ASIL NOKTA: iki sayı AYRI. Aynı değere düşerlerse tuzak geri gelmiş demektir.
    assert float(kredi["bakiye"]) == BAKIYE
    assert float(kredi["bakiye"]) != float(kredi["erken_kapama"])


def test_getiri_esiginde_de_ayri_tasiniyor():
    """Borç kapatmanın GERÇEK bedeli budur; eşik kalemleri onu görebilmeli."""
    db = _db()
    try:
        r = calculate_getiri_esigi(1, db, date(2026, 9, 2))
    finally:
        db.close()
    kalem = r["kalemler"][0]
    assert float(kalem["erken_kapama"]) == KAPAMA
    assert float(kalem["borc"]) == BAKIYE


def test_bilinmiyorsa_alan_HIC_eklenmez_sifir_yazilmaz():
    """`erken_kapama: 0` görürse koç "borcun yok" der. Bilinmeyen sıfır değildir (L45)."""
    db = _db(kapama=None)
    try:
        r = calculate_getiri_esigi(1, db, date(2026, 9, 2))
        c = generate_cockpit(1, date(2026, 9, 2), db)
    finally:
        db.close()
    assert "erken_kapama" not in r["kalemler"][0]
    assert _kredi_detayi(c)["erken_kapama"] is None


# ---- 2) KOÇ BAĞLAMI: hesap doğru ama taşınmıyorsa boşuna ----------------------
# BUG #256 sınıfı: hesap doğru, kablo kopuk. Kapı KABLOYU tutar.

def test_koc_baglaminda_tutar_VE_uyari_var():
    from app.coach import _build_context_message
    db = _db()
    try:
        ctx, _ = _build_context_message(db, 1)
    finally:
        db.close()
    assert "14.023,29" in ctx or "14023" in ctx.replace(".", ""), \
        "kapatma bedeli koç bağlamına hiç girmiyor"
    # Sayıyı vermek YETMEZ: modelin iki sayıyı karıştırdığını ÖLÇTÜK. Ayrımın kendisi
    # bağlamda yazılı olmalı, yoksa model yine `bakiye`yi kapama bedeli sanar.
    assert "KAPATMA BEDELİ" in ctx.upper()
    assert "kalan taksit toplamıdır" in ctx


def test_bilinmiyorsa_koc_BILMEDIGINI_soyler():
    from app.coach import _build_context_message
    db = _db(kapama=None)
    try:
        ctx, _ = _build_context_message(db, 1)
    finally:
        db.close()
    assert "BİLİNMİYOR" in ctx, "boş alanda koç sessiz kalıyor — tahmine açık"
    assert "tahmin etme" in ctx


# ---- 3) TEK KAYNAK: tutar `notes`a geri sızmasın -------------------------------

def test_altin_fixture_tutari_notesta_tutmuyor():
    """İki kaynak olursa biri bayatlar; hangisinin doğru olduğu belirsizleşir."""
    from scripts.coach_altin import altin_db
    db = altin_db()
    try:
        krediler = db.query(Account).filter(Account.account_type == AccountType.loan).all()
        assert krediler, "fixture'da kredi yok — kapı kör koşuyor"
        for k in krediler:
            assert k.early_payoff_amount is not None, f"{k.name}: kapama tutarı alanda yok"
            assert "Erken Kapama" not in (k.notes or ""), f"{k.name}: tutar notes'a sızmış"
    finally:
        db.close()


# ---- 4) API SÖZLEŞMESİ: alan yazılabilir ve geri okunabilir --------------------

def test_api_alani_yazip_okuyabiliyor(istemci):
    olustur = istemci.post("/api/accounts", json={
        "name": "API Kredi", "account_type": "loan", "balance": BAKIYE,
        "monthly_payment": 4109.90, "remaining_installments": 4,
        "early_payoff_amount": KAPAMA,
    })
    assert olustur.status_code in (200, 201), olustur.text
    hesap_id = olustur.json()["id"]
    assert float(olustur.json()["early_payoff_amount"]) == KAPAMA

    # Güncelleme de taşımalı — yalnız yaratmada çalışan alan yarım alandır.
    guncelle = istemci.put(f"/api/accounts/{hesap_id}",
                           json={"early_payoff_amount": 13000.0})
    assert guncelle.status_code == 200, guncelle.text
    assert float(guncelle.json()["early_payoff_amount"]) == 13000.0

    oku = istemci.get("/api/accounts")
    kayit = next(a for a in oku.json() if a["id"] == hesap_id)
    assert float(kayit["early_payoff_amount"]) == 13000.0


def test_api_negatif_tutari_reddediyor(istemci):
    """Kapatma bedeli negatif olamaz — SEC-032 doğrulaması bu alana da uygulanmalı."""
    r = istemci.post("/api/accounts", json={
        "name": "Negatif", "account_type": "loan", "balance": 1000.0,
        "early_payoff_amount": -5.0,
    })
    assert r.status_code == 422, f"negatif kapatma bedeli kabul edildi: {r.status_code}"
