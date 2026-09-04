"""
BUG #340 KAPISI — DÜZELTME VERİYE BAĞLIYDI; VERİSİ OLMAYAN KULLANICIDA ÜRÜN HÂLÂ VARSAYIYORDU.

ÖLÇÜLEN DURUM (4 Eylül 2026, canlı DB)
--------------------------------------
BUG #330 (asgari oran hesabın özelliği) ve BUG #337 (asgari EKSTRE borcundan) doğru
düzeltmelerdi — ama ikisi de **veriye bağlı**. Canlı ölçüm:

    kullanıcı A / kart-1   asgari = 1.644,23   varsayimsal = False   <- veri dolu
    kullanıcı B / kart-2   asgari = 3.984,00   varsayimsal = True
    kullanıcı C / kart-3   asgari = 5.000,00   varsayimsal = True
    kullanıcı C / kart-4   asgari = 4.875,00   varsayimsal = True

Yani **6 kullanıcının yalnız birinde** (verisini elle girenin profilinde) asgari ölçülmüş bir
sayı; kalan gerçek beta kullanıcılarında **sabit %25 yedeği** ve **güncel borç** kullanılıyor.
BUG #330 tam olarak bu sabitin yanlış olduğunu ölçmüştü: gerçek oran %20'ydi ve
kullanıcıya **411 TL fazla** asgari söylenmişti. Yedeğin kendisi meşru (L45: bilinmeyen,
sıfır değildir) — **sessiz olması değil.**

SÖZLEŞME
--------
* Yedeğe düşüldüğünde `DebtItem.asgari_varsayimsal = True` olur.
* Bayrak SAYIYI DEĞİŞTİRMEZ — yalnız sayının nereden geldiğini taşır. Davranış değişmez.
* İki bilinmeyenden HERHANGİ biri yeter: oran YA DA son ekstre borcu.
* `compare_strategies` bunu, depoda zaten var olan "FAİZSİZ varsayıldı" uyarısıyla AYNI
  desende kullanıcıya bildirir (yeni bir mekanizma icat edilmedi).
* Krediler kapsam dışı: onların taksiti `monthly_payment` alanından gelir, kart asgarisi
  gibi bir orandan türetilmez.

Bu, Murat'ın kendi koyduğu kuralın veri tarafındaki karşılığıdır:
*"varsayımla karta ya da nakite yazılmamalı, bana sormalı"* (BUG #332) — orada ürün
harcamanın hesabını varsayıyordu, burada asgarinin tabanını.
"""
from __future__ import annotations

from decimal import Decimal as D

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.debt_strategy import (MIN_CARD_PAYMENT_RATIO, asgari_oran_cozumle,
                               collect_debts, compare_strategies)
from app.models import Account, AccountType, Base, User


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="m"))
    s.commit()
    yield s
    s.close()


def _kart(db, oran=None, ekstre=None, borc="8338.13", ad="Kart", hid=1):
    db.add(Account(id=hid, user_id=1, name=ad, account_type=AccountType.credit_card,
                   balance=D(borc), credit_limit=D("12000"),
                   statement_balance=D(ekstre) if ekstre is not None else None,
                   min_payment_ratio=oran))
    db.commit()
    return collect_debts(db, 1)[0]


def test_VERI_TAMSA_varsayimsal_DEGIL(db):
    """Verisi tam kart: oran %20 + ekstre 8.221,13 → ölçülmüş sayı, bayrak kapalı."""
    d = _kart(db, oran=0.20, ekstre="8221.13")
    assert d.asgari_varsayimsal is False
    assert abs(d.min_payment - 1644.23) < 0.01


def test_ORAN_YOKSA_varsayimsaldir(db):
    """Verisi girilmemiş kullanıcıların durumu: oran girilmemiş → sabit yedek kullanıldı, bayrak açık."""
    d = _kart(db, oran=None, ekstre="8221.13")
    assert d.asgari_varsayimsal is True


def test_EKSTRE_YOKSA_oran_BILINSE_BILE_varsayimsaldir(db):
    """
    İkinci bilinmeyen ayrı ayrı yeter. Ekstre yoksa asgari GÜNCEL borçtan hesaplanır ve
    ay içi her harcama onu şişirir (BUG #337'nin ölçtüğü yön). Oranı bilmek bunu düzeltmez.
    """
    d = _kart(db, oran=0.20, ekstre=None)
    assert d.asgari_varsayimsal is True


@pytest.mark.parametrize("bozuk", [0, -0.1, 1.5, "abc"])
def test_GECERSIZ_ORAN_da_varsayimdir(bozuk):
    """Sıfır/negatif/1üstü/çöp değer yedeğe düşer — ve bu da bir varsayımdır."""
    oran, varsayimsal = asgari_oran_cozumle(bozuk)
    assert oran == MIN_CARD_PAYMENT_RATIO
    assert varsayimsal is True


def test_BAYRAK_SAYIYI_DEGISTIRMEZ(db):
    """
    L45 sözleşmesi: yedek DAVRANIŞI değiştirmez, yalnız görünür olur. Bayrak eklenirken
    asgari tutarın kayması, bir teşhis alanının ürünü sessizce oynatması olurdu (ADR-052'nin
    "karar tipte, teşhis ayrı alanda" ilkesi).
    """
    d = _kart(db, oran=None, ekstre=None, borc="8338.13")
    assert abs(d.min_payment - 8338.13 * MIN_CARD_PAYMENT_RATIO) < 0.01


def test_KREDI_asla_varsayimsal_isaretlenmez(db):
    """Kredinin taksiti orandan türetilmez; bayrağı kartlara ait tutmak kapsamı korur."""
    db.add(Account(id=9, user_id=1, name="Kredi", account_type=AccountType.loan,
                   balance=D("34688.87"), monthly_payment=D("4000"), interest_rate=5.713))
    db.commit()
    kredi = [d for d in collect_debts(db, 1) if d.account_type == "loan"][0]
    assert kredi.asgari_varsayimsal is False


def test_UYARI_kullaniciya_ULASIYOR_ve_KARTI_ADLANDIRIYOR(db):
    """
    Ölçmek yetmez, HABER VERMEK gerekir (L61). Uyarı, depodaki "FAİZSİZ varsayıldı"
    uyarısıyla aynı kanaldan çıkar ve hangi kart olduğunu YAZAR — kullanıcı hangi ekstreyi
    gireceğini bilmeli.
    """
    _kart(db, oran=None, ekstre=None, ad="Yesil Kart")
    uyarilar = compare_strategies(db, 1).get("warnings", [])
    assert any("VARSAYILDI" in u and "Yesil Kart" in u for u in uyarilar), uyarilar


def test_VERI_TAMKEN_UYARI_CIKMAZ(db):
    """
    Yanlış alarm yasağı (L22): gürültülü bir uyarı okunmaz hâle gelir ve gerçek olanı da
    götürür. Verisi tam olan kullanıcı bu cümleyi GÖRMEMELİ.
    """
    _kart(db, oran=0.20, ekstre="8221.13")
    uyarilar = compare_strategies(db, 1).get("warnings", [])
    assert not any("VARSAYILDI" in u for u in uyarilar), uyarilar


def test_KOCUN_OKUDUGU_BLOKTA_isaretli(db):
    """
    L61 — ÖLÇEN SİSTEM HABER VEREN SİSTEM DEĞİLDİR. Uyarı `compare_strategies`te vardı ama
    oraya yalnız UI bakıyor; koç `cockpit["asgari_tuzagi"]`i okur. Zarar koçun cevabında
    oluştuğuna göre bayrak O yüzeyde olmalı (bir sözleşme, ZORLANDIĞI yerde ölçülür).
    """
    from app.debt_strategy import calculate_min_payment_trap
    _kart(db, oran=None, ekstre=None, ad="Yesil Kart")
    tuzak = calculate_min_payment_trap(collect_debts(db, 1))
    assert tuzak and tuzak["kartlar"], "tuzak hesaplanmadı"
    assert tuzak["kartlar"][0]["asgari_varsayimsal"] is True


def test_KOC_BAGLAMINDA_uyari_METNI_var(db):
    """
    Bayrağın kokpitte olması yetmez — koçun gördüğü METNE girmeli, yoksa model onu hiç
    görmez (BUG #322'nin dersi: sözleşme, yazıldığı yerde değil kullanıldığı yerde ölçülür).
    """
    from app.coach import _build_context_message
    _kart(db, oran=None, ekstre=None, ad="Yesil Kart")
    metin, _ = _build_context_message(db, 1)

    # Kart adı, uyarı olmasa da tuzak satırlarında GEÇİYOR — bu yüzden "metinde var mı"
    # diye bakmak vakumsal bir yeşildir. Uyarının kendisi kartı ADLANDIRMALI, yoksa
    # kullanıcı hangi ekstreyi gireceğini bilemez.
    varsayim_satirlari = [s for s in metin.splitlines() if "VARSAYIM" in s]
    assert varsayim_satirlari, metin[-600:]
    assert any("Yesil Kart" in s for s in varsayim_satirlari), varsayim_satirlari
