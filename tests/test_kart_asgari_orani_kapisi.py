"""
BUG #330 KAPISI — KART ASGARİ ORANI KODA GÖMÜLÜ VE YANLIŞTI.

ÖLÇÜLEN DEFEKT (4 Eylül 2026, gerçek kullanıcı, gerçek para kararı):
Kullanıcı 14 Eylül'de kartına ne kadar ödeyeceğine karar veriyordu. Asistan asgariyi
`debt_strategy.MIN_CARD_PAYMENT_RATIO = 0.25` sabitinden hesapladı:

    8.221,13 × %25 = 2.055,28   ← kullanıcıya SÖYLENEN
    8.221,13 × %20 = 1.644,23   ← BANKANIN EKRANINDA YAZAN

**411,06 TL fazla.** Kullanıcı bankadan bakıp düzeltti: *"asgari tutardan kalan borç
1644.23 diyo sen yanlış mı ölçtün"*. Evet — bir KOD VARSAYIMI ölçüm sanılmıştı.

Asgari oran tek bir sabit olamaz: bankaya, kartın limitine ve yaşına göre değişir
(BDDK düzenlemesi). `interest_rate` gibi HESABIN özelliğidir. Sabit yalnızca
**bilinmiyorsa** kullanılan yedek değerdir.

SÖZLEŞME:
  * `Account.min_payment_ratio` doluysa O kullanılır.
  * NULL ise `MIN_CARD_PAYMENT_RATIO` yedeği kullanılır (davranış değişmez).
  * Oran simülasyonun HER AYINDA da geçerlidir — yoksa ilk ay doğru, sonraki aylar
    yanlış hesaplanırdı (BUG #079'un dersi: kart asgarisi her ay güncel bakiyeden).
"""
from __future__ import annotations

from decimal import Decimal as D

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.debt_strategy import (MIN_CARD_PAYMENT_RATIO, calc_avalanche,
                               collect_debts, DebtItem)
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


def _kart(db, oran=None, bakiye="8221.13"):
    db.add(Account(id=1, user_id=1, name="Kart", account_type=AccountType.credit_card,
                   balance=D(bakiye), credit_limit=D("12000"),
                   min_payment_ratio=oran))
    db.commit()


def test_HESABIN_ORANI_kullanilir_sabit_DEGIL(db):
    """Ziraat'in gerçeği: %20 → 1.644,23. Sabit %25 olsaydı 2.055,28 derdi."""
    _kart(db, oran=0.20)
    borc = collect_debts(db, 1)[0]
    assert abs(borc.min_payment - 1644.23) < 0.01, borc.min_payment


def test_ORAN_YOKSA_sabit_yedege_dusulur_davranis_degismez(db):
    """Geriye uyum: oranı bilinmeyen kartlar eskisi gibi hesaplanır."""
    _kart(db, oran=None)
    borc = collect_debts(db, 1)[0]
    assert abs(borc.min_payment - 8221.13 * MIN_CARD_PAYMENT_RATIO) < 0.01, borc.min_payment


def test_ORAN_SIMULASYONUN_HER_AYINDA_gecerli():
    """
    BUG #079'un dersi: kart asgarisi her ay GÜNCEL bakiyeden hesaplanır. Oran yalnız
    `collect_debts`te uygulanıp simülasyonda sabite düşerse, ilk ay doğru sonraki aylar
    yanlış olur — ve bu, ödeme planının tamamını sessizce kaydırır.
    """
    dusuk = DebtItem(account_id=1, name="K", account_type="credit_card", balance=10000.0,
                     interest_rate_monthly=4.25, min_payment=2000.0, min_payment_ratio=0.20)
    yuksek = DebtItem(account_id=1, name="K", account_type="credit_card", balance=10000.0,
                      interest_rate_monthly=4.25, min_payment=2500.0, min_payment_ratio=0.25)
    a = calc_avalanche([dusuk], extra_monthly=0.0)
    b = calc_avalanche([yuksek], extra_monthly=0.0)
    assert a.months_to_freedom > b.months_to_freedom, (
        "oran simülasyonda kullanılmıyor — %20 ödeyen kart %25 ödeyenle aynı sürede bitiyor")


def test_ORAN_ARALIGI_makul(db):
    """Sıfır/negatif/1'den büyük oran kabul edilemez — sessizce bozuk plan üretirdi."""
    from app.debt_strategy import gecerli_asgari_oran
    assert gecerli_asgari_oran(0.20) == 0.20
    assert gecerli_asgari_oran(None) == MIN_CARD_PAYMENT_RATIO
    assert gecerli_asgari_oran(0) == MIN_CARD_PAYMENT_RATIO
    assert gecerli_asgari_oran(-0.1) == MIN_CARD_PAYMENT_RATIO
    assert gecerli_asgari_oran(1.5) == MIN_CARD_PAYMENT_RATIO


def test_CANLI_KULLANICININ_KARTI_dogru_orani_tasiyor():
    """
    Bu tur bir ÜRÜN düzeltmesi kadar bir VERİ düzeltmesiydi: kullanıcının gerçek kartı
    %20 taşımalı, yoksa koç yine 411 TL fazla asgari söyler.
    """
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent
    if not (kok / "data" / "financialos.db").exists():
        pytest.skip("canlı DB yok (taze klon)")
    import sqlite3
    c = sqlite3.connect(kok / "data" / "financialos.db")
    try:
        satir = c.execute(
            "select min_payment_ratio from accounts where user_id=5 and name like 'Ziraat Kredi Kart%'"
        ).fetchone()
    finally:
        c.close()
    assert satir and satir[0] == 0.20, f"canlı kartta oran {satir} — %20 olmalı (banka ekranı)"
