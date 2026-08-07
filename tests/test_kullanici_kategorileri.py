"""
P3.5.3 — BUG #264 / ADR-046: KATEGORİ KULLANICIYA AİT BİR KAYITTIR.

ÖLÇÜLEN GERÇEKLİK (iddia değil): kod, kullanıcının parasıyla ilgili iki kararı sabit
Türkçe kategori ADLARINA bağlıyordu.

  1. `action_executor._CARD_CATEGORIES = {"yemek","eglence","sigara","alisveris","market"}`
     → koçun kaydettiği harcamanın KREDİ KARTINA yazılıp yazılmayacağı. Kendi kategorisini
     adlandıran kullanıcı ("gıda") bu kümeye hiç düşmez → yönlendirme sessizce ölür.
     Tersi de doğru: "market" adını kullanan ama o harcamayı NAKİT yapan kullanıcının
     parası kart borcuna yazılır ve iki bakiye birden yanlış olur.
  2. `rules_engine._PATTERN_EXCLUDED_CATEGORIES` → hangi harcamanın "artış" uyarısına
     gireceği. Aynı sınıf: kullanıcı "borç ödeme"yi kendi diliyle adlandırdığı an dışlama
     ölür ve borç ödemesi kişisel harcama artışı sayılır.

KİLİTLENEN SÖZLEŞME:
  1. Karar ADDA değil BAYRAKTA (`Category.kart_varsayilani` / `Category.sistem`).
  2. Varsayılan set BUGÜNKÜ davranışı birebir üretir (göç davranış değiştirmez).
  3. Okuma yolu (rules_engine) DB'ye YAZMAZ — tohumlama okumadan tetiklenmez.
  4. Kullanılmış kategori hedefsiz silinemez (işlemler kategorisiz kalırdı — L2).
  5. Sistem kategorisi silinemez/yeniden adlandırılamaz; yalnız gizlenebilir.
  6. Kategori seti defter kapsamlıdır — başka kullanıcının seti görünmez/değişmez (L1).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.action_executor import _normalize_transaction_payload
from app.category_rules import (
    kart_varsayilani_mi,
    kategori_haritasi,
    kategorileri_tohumla,
    normalize,
    sistem_kategorisi_mi,
    sistem_slug_kumesi,
    varsayilan_set,
)
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import (
    Account, AccountType, Base, Category, Envelope, Transaction, TransactionType, User,
)
from app.rules_engine import _calculate_category_patterns

TODAY = date(2026, 6, 1)
CURR = TODAY - timedelta(days=10)   # curr penceresi ([today-29, today]) içinde
PREV = TODAY - timedelta(days=45)   # prev penceresi ([today-59, today-30]) içinde


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="kullanici"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def tohumlu_db(db):
    kategorileri_tohumla(db, 1)
    db.commit()
    return db


def _kategori(db, slug, user_id=1):
    return db.query(Category).filter(
        Category.user_id == user_id, Category.slug == slug).one()


def _harcama(db, category, amount, when, n=1, user_id=1):
    for _ in range(n):
        db.add(Transaction(user_id=user_id, transaction_type=TransactionType.expense,
                           amount=amount, category=category, transaction_date=when))
    db.commit()


# ============================================================================
# A) GÖÇ DAVRANIŞI DEĞİŞTİRMEZ — varsayılan set = eski sabit kümeler
# ============================================================================

# BUG #264 öncesi üretim kodundaki sabit kümeler (tarihsel kopya — kaynak: git geçmişi).
_ESKI_CARD_CATEGORIES = {"yemek", "eglence", "sigara", "alisveris", "market"}
_ESKI_PATTERN_EXCLUDED = {
    "kredi_taksiti", "loan_payment", "debt_payment", "borc_odeme",
    "borc", "kredi", "transfer",
}


def test_varsayilan_set_eski_kart_kumesini_birebir_uretir(tohumlu_db):
    """Göç kanıtı: kart varsayılanı olan slug'lar = eski `_CARD_CATEGORIES`."""
    kart = {s for s, k in kategori_haritasi(tohumlu_db, 1).items() if k["kart_varsayilani"]}
    assert kart == _ESKI_CARD_CATEGORIES


def test_varsayilan_set_eski_dislama_kumesini_KAPSAR(tohumlu_db):
    """Sistem kategorileri eski dışlama kümesinin tamamını içerir (davranış korunur).

    Fazlası var ve bu BİLİNÇLİ: `borc_geri_odeme` (hızlı girişin ürettiği slug) eski
    listede YOKTU — borç ödemesi kişisel harcama paterni sayılıyordu. Bu bir defektti,
    sınıf taramasında bulundu ve kapatıldı.
    """
    sistem = sistem_slug_kumesi(tohumlu_db, 1)
    assert _ESKI_PATTERN_EXCLUDED <= sistem
    assert "borc_geri_odeme" in sistem, "hızlı girişin borç slug'ı dışlanmıyordu (defekt)"


def test_kayit_yoksa_varsayilan_haritaya_duser(db):
    """Kaydı olmayan defterde davranış bugünküyle aynı (belgeli fallback)."""
    assert kart_varsayilani_mi(db, 1, "market") is True
    assert sistem_kategorisi_mi(db, 1, "transfer") is True


def test_okuma_yolu_DB_YE_YAZMAZ(db):
    """rules_engine sözleşmesi: okuma tohumlama TETİKLEMEZ (app/PROJE.md)."""
    yazmalar = []
    event.listen(db, "after_flush", lambda s, c: yazmalar.append(len(s.new)))

    kategori_haritasi(db, 1)
    sistem_slug_kumesi(db, 1)
    kart_varsayilani_mi(db, 1, "market")
    db.flush()

    assert db.query(Category).count() == 0, "okuma yolu kategori tohumladı"
    assert not any(yazmalar), "okuma yolu flush'ta yeni satır üretti"


# ============================================================================
# B) ASIL DEFEKT — PARA kararı artık kullanıcının
# ============================================================================

def _kart_ve_nakit(db, user_id=1):
    db.add(Account(id=1, user_id=user_id, name="Nakit", account_type=AccountType.cash,
                   balance=5000))
    db.add(Account(id=2, user_id=user_id, name="Kart", account_type=AccountType.credit_card,
                   balance=0))
    db.commit()


def test_kart_varsayilani_kapatilinca_harcama_karta_YAZILMAZ(tohumlu_db):
    """BUG #264 çekirdeği: kullanıcı 'market' harcamalarını nakit yapıyorsa bunu SÖYLEYEBİLİR.

    Eskiden imkânsızdı — 'market' beş sabit addan biriydi ve harcama koşulsuz kart
    borcuna yazılıyordu (nakit VE kart bakiyesi birden yanlış olurdu).
    """
    _kart_ve_nakit(tohumlu_db)
    _kategori(tohumlu_db, "market").kart_varsayilani = False
    tohumlu_db.commit()

    payload = _normalize_transaction_payload({"category": "market", "amount": 300},
                                             user_id=1, db=tohumlu_db)
    assert "account_id" not in payload or payload.get("account_id") is None
    assert payload.get("is_card_expense") is not True


def test_kullanicinin_KENDI_kategorisi_kart_varsayilani_olabilir(tohumlu_db):
    """Simetrik yön: 'gıda' diye adlandıran kullanıcıda da kural çalışır (eskiden ölüydü)."""
    _kart_ve_nakit(tohumlu_db)
    tohumlu_db.add(Category(user_id=1, slug="gida", ad="Gıda", kart_varsayilani=True))
    tohumlu_db.commit()

    payload = _normalize_transaction_payload({"category": "Gıda", "amount": 300},
                                             user_id=1, db=tohumlu_db)
    assert payload["account_id"] == 2          # kredi kartı
    assert payload["is_card_expense"] is True
    assert payload["category"] == "gida"       # normalize edilmiş slug yazılır (BUG #026)


def test_tanimsiz_kategori_parayi_karta_YAZMAZ(tohumlu_db):
    """Bilinmeyen ad için varsayım yasak (§1.1) — kullanıcının tanımlamadığı kategori
    kart varsayılanı değildir."""
    _kart_ve_nakit(tohumlu_db)
    payload = _normalize_transaction_payload({"category": "kitap", "amount": 120},
                                             user_id=1, db=tohumlu_db)
    assert payload.get("is_card_expense") is not True


def test_varsayilan_kurulumda_eski_davranis_AYNEN_surer(tohumlu_db):
    """Hiçbir şey değiştirmeyen kullanıcı için davranış birebir aynı kalır."""
    _kart_ve_nakit(tohumlu_db)
    payload = _normalize_transaction_payload({"category": "Yemek", "amount": 250},
                                             user_id=1, db=tohumlu_db)
    assert payload["account_id"] == 2
    assert payload["is_card_expense"] is True


# ============================================================================
# C) UYARI kararı — muhasebe işlemi harcama paterni değildir
# ============================================================================

def test_borc_geri_odeme_harcama_paterninden_DISLANIR(tohumlu_db):
    """Eski dışlama listesinde `borc_geri_odeme` YOKTU → borç ödemesi 'harcaman arttı'
    uyarısını tetikleyebiliyordu. Sistem bayrağıyla kapandı."""
    _harcama(tohumlu_db, "borc_geri_odeme", 1000.0, PREV, n=2)
    _harcama(tohumlu_db, "borc_geri_odeme", 3000.0, CURR, n=3)

    kategoriler = {p["category"] for p in _calculate_category_patterns(1, TODAY, tohumlu_db)}
    assert "borc_geri_odeme" not in kategoriler


def test_kullanici_kendi_muhasebe_kategorisini_dislayabilir(tohumlu_db):
    """Kullanıcı 'borç kapama' diye adlandırdıysa da dışlayabilir (eskiden ada bağlıydı)."""
    tohumlu_db.add(Category(user_id=1, slug="borc kapama", ad="Borç kapama", sistem=True))
    tohumlu_db.commit()
    _harcama(tohumlu_db, "borc kapama", 500.0, PREV, n=2)
    _harcama(tohumlu_db, "borc kapama", 1500.0, CURR, n=3)

    kategoriler = {p["category"] for p in _calculate_category_patterns(1, TODAY, tohumlu_db)}
    assert "borc kapama" not in kategoriler


def test_normal_kategori_paternde_KALIR(tohumlu_db):
    """Dışlama fazla geniş olmamalı — gerçek harcama analizden düşmez."""
    _harcama(tohumlu_db, "yemek", 500.0, PREV, n=2)
    _harcama(tohumlu_db, "yemek", 700.0, CURR, n=3)

    kategoriler = {p["category"] for p in _calculate_category_patterns(1, TODAY, tohumlu_db)}
    assert "yemek" in kategoriler


# ============================================================================
# D) TOHUMLAMA
# ============================================================================

def test_tohumlama_idempotent_ve_kullanici_duzenlemesini_EZMEZ(tohumlu_db):
    kayit = _kategori(tohumlu_db, "market")
    kayit.ad = "Bakkal"
    kayit.kart_varsayilani = False
    tohumlu_db.commit()
    onceki_sayi = tohumlu_db.query(Category).count()

    eklenen = kategorileri_tohumla(tohumlu_db, 1)
    tohumlu_db.commit()

    assert eklenen == 0
    assert tohumlu_db.query(Category).count() == onceki_sayi
    yeniden = _kategori(tohumlu_db, "market")
    assert yeniden.ad == "Bakkal"
    assert yeniden.kart_varsayilani is False


def test_tohum_seti_slug_tekil_ve_normalize(db):
    sluglar = [t["slug"] for t in varsayilan_set()]
    assert len(sluglar) == len(set(sluglar)), "varsayılan sette çift slug var"
    for s in sluglar:
        assert normalize(s) == s, f"slug normalize değil: {s}"


def test_categories_tablosu_semada_var(db):
    assert "categories" in inspect(db.get_bind()).get_table_names()


# ============================================================================
# E) API — CRUD, birleştirme, sistem koruması, izolasyon
# ============================================================================

@pytest.fixture
def istemci(tohumlu_db):
    kullanici = tohumlu_db.get(User, 1)  # SQLAlchemy 2.x (app/PROJE.md)
    app.dependency_overrides[get_db] = lambda: tohumlu_db
    app.dependency_overrides[get_current_user] = lambda: kullanici
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_liste_gizlileri_haric_tutar(istemci, tohumlu_db):
    _kategori(tohumlu_db, "sigara").gizli = True
    tohumlu_db.commit()

    gorunen = {c["slug"] for c in istemci.get("/api/categories").json()}
    tumu = {c["slug"] for c in istemci.get("/api/categories?tumu=true").json()}

    assert "sigara" not in gorunen
    assert "sigara" in tumu


def test_yeni_kategori_slug_normalize_edilir(istemci):
    r = istemci.post("/api/categories", json={"ad": "Öğle Yemeği", "kart_varsayilani": True})
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "ogle yemegi"   # BUG #167: Kiril 'о' değil ASCII 'o'
    assert r.json()["ad"] == "Öğle Yemeği"


def test_ayni_slug_409(istemci):
    assert istemci.post("/api/categories", json={"ad": "yemek"}).status_code == 409


def test_gizli_kategori_yeniden_eklenince_GERI_ACILIR(istemci, tohumlu_db):
    """Yeni satır açmak geçmişi ikiye bölerdi — aynı slug geri açılır."""
    _kategori(tohumlu_db, "kira").gizli = True
    tohumlu_db.commit()

    r = istemci.post("/api/categories", json={"ad": "Kira"})
    assert r.status_code == 201
    assert tohumlu_db.query(Category).filter(Category.slug == "kira").count() == 1
    assert _kategori(tohumlu_db, "kira").gizli is False


def test_sistem_kategorisi_yeniden_adlandirilamaz(istemci, tohumlu_db):
    transfer = _kategori(tohumlu_db, "transfer")
    r = istemci.patch(f"/api/categories/{transfer.id}", json={"ad": "Aktarma"})
    assert r.status_code == 409


def test_sistem_kategorisi_silinemez_ama_gizlenebilir(istemci, tohumlu_db):
    transfer = _kategori(tohumlu_db, "transfer")
    assert istemci.delete(f"/api/categories/{transfer.id}").status_code == 409
    assert istemci.patch(f"/api/categories/{transfer.id}", json={"gizli": True}).status_code == 200


def test_kullanilmis_kategori_HEDEFSIZ_silinemez(istemci, tohumlu_db):
    _harcama(tohumlu_db, "yemek", 100.0, CURR)
    yemek = _kategori(tohumlu_db, "yemek")

    r = istemci.delete(f"/api/categories/{yemek.id}")
    assert r.status_code == 409
    assert "hedef" in r.json()["detail"].lower()
    assert tohumlu_db.query(Transaction).filter(Transaction.category == "yemek").count() == 1


def test_hedefli_silme_islemleri_TASIR(istemci, tohumlu_db):
    _harcama(tohumlu_db, "yemek", 100.0, CURR, n=2)
    yemek = _kategori(tohumlu_db, "yemek")

    r = istemci.delete(f"/api/categories/{yemek.id}?hedef=alisveris")
    assert r.status_code == 204, r.text
    assert tohumlu_db.query(Transaction).filter(Transaction.category == "yemek").count() == 0
    assert tohumlu_db.query(Transaction).filter(Transaction.category == "alisveris").count() == 2
    assert tohumlu_db.query(Category).filter(Category.slug == "yemek").count() == 0


def test_hedefli_silme_zarf_butcesini_de_tasir(istemci, tohumlu_db):
    _harcama(tohumlu_db, "yemek", 100.0, CURR)
    tohumlu_db.add(Envelope(user_id=1, category="yemek", monthly_amount=2000))
    tohumlu_db.commit()
    yemek = _kategori(tohumlu_db, "yemek")

    assert istemci.delete(f"/api/categories/{yemek.id}?hedef=alisveris").status_code == 204
    zarflar = {e.category for e in tohumlu_db.query(Envelope).all()}
    assert zarflar == {"alisveris"}


def test_bilinmeyen_hedef_404(istemci, tohumlu_db):
    _harcama(tohumlu_db, "yemek", 100.0, CURR)
    yemek = _kategori(tohumlu_db, "yemek")
    assert istemci.delete(f"/api/categories/{yemek.id}?hedef=yokboyle").status_code == 404


def test_kullanilmamis_kategori_hedefsiz_silinebilir(istemci, tohumlu_db):
    kira = _kategori(tohumlu_db, "kira")
    assert istemci.delete(f"/api/categories/{kira.id}").status_code == 204


def test_baska_kullanicinin_kategorisi_gorunmez_ve_silinemez(istemci, tohumlu_db):
    """L1: ikinci kullanıcı geldiğinde ne bozulur? — set defter kapsamlıdır."""
    tohumlu_db.add(User(id=2, name="baskasi"))
    tohumlu_db.commit()
    kategorileri_tohumla(tohumlu_db, 2)
    tohumlu_db.commit()
    yabanci = _kategori(tohumlu_db, "kira", user_id=2)

    sluglar = istemci.get("/api/categories?tumu=true").json()
    assert all(c["id"] != yabanci.id for c in sluglar)
    assert istemci.delete(f"/api/categories/{yabanci.id}").status_code == 404
    assert istemci.patch(f"/api/categories/{yabanci.id}", json={"ad": "X"}).status_code == 404
