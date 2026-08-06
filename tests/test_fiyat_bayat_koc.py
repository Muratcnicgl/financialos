"""
D23 (BUG #239) — KOÇ, SAĞLAYICI ÇÖKTÜĞÜNDE HAFTALARCA ESKİ FİYATI "GÜNCEL" GİBİ SUNUYORDU.

TEFAS/İş Yatırım/yfinance düştüğünde sağlayıcılar sessizce None döner ve `current_price`
olduğu yerde kalır. Koç bu durumda 30 gün önceki fiyatla hesaplanmış "yatırım değerin X TL,
%Y kârdasın" cümlesini KOŞULSUZ kuruyordu. Kullanıcı bu rakama göre satış/alım kararı
verirse doğrudan para kaybeder.

Projenin kendi ilkesi (BUG #211, döviz tarafı): "bayat değeri şu anki diye sunmak, hiç
sunmamaktan daha kötüdür." Aynı disiplin fiyat/portföy yolunda yoktu.

KÖK SEBEP YAPISALDI (L18): bayatlık verisi (`is_stale`, `age_text`) YALNIZ HTTP katmanında,
`generate_cockpit`'ten SONRA router'da hesaplanıyordu (`routers/cockpit.py`). Koç, premortem
ve snapshot yolları `generate_cockpit`'i DOĞRUDAN çağırdığı için bu alan onlara hiç ulaşmıyordu
— yani veri VARDI, tüketiciye ULAŞMIYORDU. Bu yüzden fix tüketicide değil KAYNAKTA: tazelik
artık cockpit sözleşmesinin parçası, her tüketici otomatik görüyor.

Bu dosya üç ucu kilitler:
  1. Kaynak (rules_engine): her yatırım hesabı + her K/Z satırı tazelik taşır.
  2. Koç dili: bayat fiyat işaretlenir + "şu anki/güncel" demesi yasaklanır; TAZE fiyatta
     bu gürültü ÇIKMAZ (mutasyon kontrolü — "hep bayat yaz" ile geçilemez).
  3. Sınıf taraması (L11): cockpit'i doğrudan tüketen LLM yolları (koç + premortem snapshot)
     tazelikten haberdar; kapsam tabanı assert'li — yeni yatırım hesabı sunan yol eklenirse
     bu kapı kırılır.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType
from app.rules_engine import generate_cockpit


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def kullanici(db):
    u = User(name="murat", email="m@x.com")
    db.add(u)
    db.commit()
    return u


def _yatirim(db, user, *, ad, yas_gun, fiyat=5223.81, lot=6.0, maliyet=4000.0,
             emanet=False, kod="TLY"):
    """Fiyatı `yas_gun` gün önce güncellenmiş yatırım hesabı."""
    acc = Account(
        user_id=user.id, name=ad, account_type=AccountType.investment,
        fund_code=kod, lot_count=lot, current_price=fiyat, cost_per_lot=maliyet,
        balance=round(lot * fiyat, 2), is_emanet=emanet,
        last_price_update=datetime.utcnow() - timedelta(days=yas_gun),
    )
    db.add(acc)
    db.commit()
    return acc


def _cockpit(db, user):
    return generate_cockpit(user.id, date(2026, 8, 6), db)


def _hesap(cockpit, ad):
    return next(a for a in cockpit["accounts"] if a["ad"] == ad)


# ── 1. KAYNAK: tazelik cockpit sözleşmesinin parçası ────────────────────────────

def test_cockpit_bayat_fiyati_isaretler(db, kullanici):
    """30 gün eski fiyat, cockpit'in KENDİSİNDE bayat işaretli gelmeli (router'da değil)."""
    _yatirim(db, kullanici, ad="TLY Fonu", yas_gun=30)
    detay = _hesap(_cockpit(db, kullanici), "TLY Fonu")
    assert detay["fiyat_bayat"] is True
    assert "30 gün önce" in detay["fiyat_yas"]


def test_cockpit_taze_fiyati_bayat_saymaz(db, kullanici):
    """Mutasyon kontrolü: 'hep bayat' yazan bir uygulama bu testi geçemez."""
    _yatirim(db, kullanici, ad="Taze Fon", yas_gun=0)
    detay = _hesap(_cockpit(db, kullanici), "Taze Fon")
    assert detay["fiyat_bayat"] is False
    assert detay["fiyat_yas"]  # yaş metni taze halde de dolu (koç "az önce" diyebilsin)


def test_hic_fiyat_girilmemis_hesap_bayat_sayilir(db, kullanici):
    acc = Account(user_id=kullanici.id, name="Boş Fon", account_type=AccountType.investment,
                  fund_code="ABC", lot_count=1.0, current_price=100.0, balance=100.0,
                  last_price_update=None)
    db.add(acc)
    db.commit()
    detay = _hesap(_cockpit(db, kullanici), "Boş Fon")
    assert detay["fiyat_bayat"] is True
    assert "girilmedi" in detay["fiyat_yas"]


def test_kz_satiri_da_tazelik_tasir(db, kullanici):
    """K/Z satırı ("%30 kârdasın") bayat fiyattan üretiliyorsa bunu taşımalı."""
    _yatirim(db, kullanici, ad="TLY Fonu", yas_gun=30)
    pnl = _cockpit(db, kullanici)["investment_pnl"][0]
    assert pnl["fiyat_bayat"] is True and "30 gün önce" in pnl["fiyat_yas"]


def test_cockpit_ozeti_bayat_var_der(db, kullanici):
    _yatirim(db, kullanici, ad="Eski", yas_gun=30)
    _yatirim(db, kullanici, ad="Taze", yas_gun=0, kod="XYZ")
    ozet = _cockpit(db, kullanici)["fiyat_tazeligi"]
    assert ozet["bayat_var"] is True and ozet["bayat_sayisi"] == 1
    assert "30 gün önce" in ozet["en_eski_yas"]


def test_yatirimsiz_kullanicida_ozet_sessiz(db, kullanici):
    ozet = _cockpit(db, kullanici)["fiyat_tazeligi"]
    assert ozet["bayat_var"] is False and ozet["bayat_sayisi"] == 0


# ── 2. UYARI EŞİĞİ: hafta sonu gürültüsü alarm üretmez ─────────────────────────

def test_uzun_susma_uyari_uretir(db, kullanici):
    """Sağlayıcı günlerce sustuysa kullanıcı bunu panelde de görmeli."""
    _yatirim(db, kullanici, ad="Eski", yas_gun=10)
    alerts = _cockpit(db, kullanici)["alerts"]
    assert any("fiyat" in (a.get("baslik", "") + a.get("mesaj", "")).lower() for a in alerts), \
        "Haftalarca susan fiyat sağlayıcısı için hiçbir uyarı yok"


def test_hafta_sonu_gurultusu_uyari_uretmez(db, kullanici):
    """TEFAS hafta sonu yayın yapmaz; 30 saatlik yaş normaldir → alarm yorgunluğu yaratma."""
    _yatirim(db, kullanici, ad="Cuma", yas_gun=0)
    acc = db.query(Account).filter(Account.name == "Cuma").one()
    acc.last_price_update = datetime.utcnow() - timedelta(hours=30)
    db.commit()
    alerts = _cockpit(db, kullanici)["alerts"]
    assert not any("fiyat" in (a.get("baslik", "") + a.get("mesaj", "")).lower() for a in alerts)


# ── 3. KOÇ DİLİ: bayat fiyat "şu anki değer" diye sunulamaz ────────────────────

def _koc_baglami(db, user):
    from app.coach import _build_context_message
    metin, _ = _build_context_message(db, user.id)
    return metin


def test_koc_baglami_bayat_fiyati_acikca_soyler(db, kullanici):
    _yatirim(db, kullanici, ad="TLY Fonu", yas_gun=30)
    metin = _koc_baglami(db, kullanici)
    assert "BAYAT" in metin, "Koç 30 günlük fiyatı 'güncel' gibi sunuyor"
    assert "30 gün önce" in metin
    satir = next(s for s in metin.splitlines() if "TLY Fonu" in s and "lot" in s)
    assert "BAYAT" in satir, "Hesap satırının kendisi bayatlığı taşımıyor"


def test_koc_baglami_bayatta_guncel_demeyi_yasaklar(db, kullanici):
    """FX yolundaki disiplinin (BUG #211) aynısı: dil değişmezse rakam yine 'şu anki' olur."""
    _yatirim(db, kullanici, ad="TLY Fonu", yas_gun=30)
    metin = _koc_baglami(db, kullanici)
    assert "şu anki" in metin.lower() and "deme" in metin.lower(), \
        "Bayat fiyatta koça 'şu anki/güncel DEME' talimatı verilmiyor"


def test_koc_baglami_kz_satirinda_da_isaretli(db, kullanici):
    """'%30 kârdasın' cümlesi bayat fiyattan üretiliyorsa işaretsiz kalamaz."""
    _yatirim(db, kullanici, ad="TLY Fonu", yas_gun=30)
    metin = _koc_baglami(db, kullanici)
    satir = next(s for s in metin.splitlines() if "brüt kâr" in s)
    assert "BAYAT" in satir


def test_koc_baglami_taze_fiyatta_bayat_demez(db, kullanici):
    """Mutasyon kontrolü: koşulsuz uyarı, uyarıyı değersizleştirir."""
    _yatirim(db, kullanici, ad="Taze Fon", yas_gun=0)
    metin = _koc_baglami(db, kullanici)
    assert "BAYAT" not in metin


# ── 4. SINIF TARAMASI (L11): cockpit'i tüketen diğer LLM yolları ───────────────

def test_premortem_snapshotu_bayatlik_tasir(db, kullanici):
    """Premortem 'net değerin X TL' der; o X bayat fiyattan geliyorsa bilinmeli."""
    from app.cockpit_snapshot import build_cockpit_snapshot
    _yatirim(db, kullanici, ad="TLY Fonu", yas_gun=30)
    snap = build_cockpit_snapshot(db, kullanici.id)
    assert snap["investment_price_stale"] is True
    assert "30 gün önce" in (snap["investment_price_age"] or "")


def test_premortem_prompti_bayatligi_yazar():
    from app.premortem import _user_prompt
    p = _user_prompt({"action_type": "satis", "aciklama": "TLY sat"},
                     {"net_worth_tl": 100000.0, "investment_tl": 31342.86,
                      "investment_price_stale": True, "investment_price_age": "30 gün önce"})
    assert "BAYAT" in p and "30 gün önce" in p


def test_premortem_prompti_taze_veride_susar():
    from app.premortem import _user_prompt
    p = _user_prompt({"action_type": "satis", "aciklama": "TLY sat"},
                     {"net_worth_tl": 100000.0, "investment_tl": 31342.86,
                      "investment_price_stale": False, "investment_price_age": "az önce"})
    assert "BAYAT" not in p


def test_hesaplar_ucu_tazelik_doner(db, kullanici):
    """Panel `fiyat_bayat`/`fiyat_yas` okuyor — uç bunları GERÇEKTEN gönderiyor mu?

    BUG #232/#233 dersi: sunucu ve istemci ayrı ayrı doğru olup uyuşmazlık ARADA
    kalabiliyor. O yüzden sözleşme iki taraftan da teste bağlanır."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_db, get_current_user

    _yatirim(db, kullanici, ad="TLY Fonu", yas_gun=30)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: kullanici
    try:
        r = TestClient(app).get("/api/accounts")
        assert r.status_code == 200
        fon = next(a for a in r.json() if a["name"] == "TLY Fonu")
        assert fon["fiyat_bayat"] is True and "30 gün önce" in fon["fiyat_yas"]
    finally:
        app.dependency_overrides.clear()


def test_hesaplar_ucu_nakitte_fiyat_yasi_uydurmaz(db, kullanici):
    """Mutasyon kontrolü: nakit hesabın `last_price_update`'i yoktur — 'henüz girilmedi'
    diye bayat işaretlenirse panel her nakit kartında anlamsız uyarı gösterir."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_db, get_current_user

    db.add(Account(user_id=kullanici.id, name="Nakit", account_type=AccountType.cash,
                   balance=1000.0))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: kullanici
    try:
        nakit = next(a for a in TestClient(app).get("/api/accounts").json()
                     if a["name"] == "Nakit")
        assert nakit["fiyat_bayat"] is False and nakit["fiyat_yas"] is None
    finally:
        app.dependency_overrides.clear()


def test_kapsam_tabani_her_yatirim_hesabi_tazelik_tasir(db, kullanici):
    """L11 kapsam tabanı: cockpit'te fiyat sunan HER hesap tazelik alanlarını taşımalı.

    Yeni bir yatırım sunum yolu eklenip tazelik unutulursa bu kapı kırılır."""
    _yatirim(db, kullanici, ad="A", yas_gun=30)
    _yatirim(db, kullanici, ad="B", yas_gun=0, kod="XYZ")
    _yatirim(db, kullanici, ad="C", yas_gun=5, kod="EMN", emanet=True)
    cockpit = _cockpit(db, kullanici)
    fiyatli = [a for a in cockpit["accounts"] if a.get("fiyat") is not None]
    assert len(fiyatli) == 3, "Kapsam tabanı kaydı: 3 yatırım hesabı bekleniyordu"
    for a in fiyatli:
        assert "fiyat_bayat" in a and "fiyat_yas" in a, f"{a['ad']} tazelik taşımıyor"
