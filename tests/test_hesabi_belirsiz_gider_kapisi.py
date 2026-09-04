"""
BUG #332 KAPISI — "HESABI O AN BELLİ OLUR" DİYE BİR SEÇENEK YOKTU; ÜRÜN VARSAYIYORDU.

KULLANICI İSTEĞİ (4 Eylül 2026, birebir): *"harcamalar kart mı nakit mi o anlık karar
verilen bir şey; seçenek olarak önerirse eğer bana sormalı, varsayımla karta ya da nakite
yazılmamalı."*

ÖLÇÜLEN DURUM: `RecurringExpense.account_id` **zorunluydu** (`nullable=False`). Yani
"sigara" gibi bazen kartla bazen nakitle yapılan bir harcamayı sisteme girmek için bir
hesap SEÇMEK gerekiyordu — ve bu seçim bir varsayımdı. Asistan da bunu yaptı: kullanıcının
üç yaşam giderini karta bağladı. Kullanıcı bunu fark edip düzeltilmesini istedi.

TASARIM — ÜÇ KOVA, HİÇBİRİ SESSİZ DEĞİL:
    nakit hesabı  -> nakit takvimine ÇIKIŞ (eskisi gibi)
    kart hesabı   -> `karta_yazilacak` (BUG #331: bu ay nakit azalmaz, borç büyür)
    BOŞ (NULL)    -> `hesabi_belirsiz`: İKİSİNE DE sayılmaz, AYRI gösterilir

Üçüncü kovanın bakiyeye girmemesi bilinçli ve iki yönlü gerekçesi var:
  · Nakit sayarsak olmayan bir açık üretiriz (BUG #331'de tam olarak bu oldu).
  · Kart sayarsak nakit yeterliymiş gibi görünür, oysa nakitten çıkabilir.
İkisi de bir VARSAYIMDIR. Doğrusu: sayma, GÖSTER, kullanıcıya sor. Koç böylece
"nakdin yetiyor ama hesabı belirsiz 8.800 TL harcaman var" diyebilir.

Bu, `HesapBelirsiz` (BUG #042) korumasının düzenli-gider yolundaki karşılığıdır: orada
kullanıcı "500 harcadım" deyince koç "hangi hesaptan?" diye soruyor; burada da öyle olmalı.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Account, AccountType, Base, RecurringExpense, User
from app.rules_engine import calculate_nakit_takvimi


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="m"))
    s.add(Account(id=1, user_id=1, name="Nakit", account_type=AccountType.cash,
                  balance=D("10000")))
    s.add(Account(id=2, user_id=1, name="Kart", account_type=AccountType.credit_card,
                  balance=D("0"), credit_limit=D("12000"), payment_day=14))
    s.commit()
    yield s
    s.close()


def _gider(db, ad, tutar, hesap_id, gun=15):
    db.add(RecurringExpense(user_id=1, name=ad, amount=D(str(tutar)),
                            account_id=hesap_id, day_of_month=gun, is_active=True))
    db.commit()


def test_HESAP_BOS_BIRAKILABILIR(db):
    """Sözleşmenin temeli: 'bilmiyorum' geçerli bir cevap olmalı."""
    _gider(db, "Sigara", 3600, hesap_id=None)
    assert db.query(RecurringExpense).one().account_id is None


def test_BELIRSIZ_gider_NAKIT_cikisi_sayilmaz(db):
    """Nakit saymak, BUG #331'de ölçülen sahte açığı geri getirirdi."""
    _gider(db, "Sigara", 3600, hesap_id=None)
    t = calculate_nakit_takvimi(1, db, date(2026, 9, 4))
    assert all(k["ad"] != "Sigara" for k in t["kalemler"])
    assert t["ay_sonu_bakiye"] == D("10000")


def test_BELIRSIZ_gider_KARTA_da_sayilmaz(db):
    """Kart saymak da bir varsayımdır — sadece ters yönde."""
    _gider(db, "Sigara", 3600, hesap_id=None)
    t = calculate_nakit_takvimi(1, db, date(2026, 9, 4))
    assert t["karta_yazilacak_toplam"] == D("0")


def test_BELIRSIZ_gider_GORUNMEZ_OLMAZ(db):
    """
    Saymamak, yok saymak DEĞİLDİR. Görünmeyen bir kalem, olmayan bir kalemden
    tehlikelidir (BUG #320/#331'in aynı ilkesi).
    """
    _gider(db, "Sigara", 3600, hesap_id=None)
    _gider(db, "Kahve", 1200, hesap_id=None)
    t = calculate_nakit_takvimi(1, db, date(2026, 9, 4))
    assert t["hesabi_belirsiz_toplam"] == D("4800")
    assert {k["ad"] for k in t["hesabi_belirsiz"]} == {"Sigara", "Kahve"}


def test_UC_KOVA_birbirine_KARISMAZ(db):
    _gider(db, "Kira", 5000, hesap_id=1)        # nakit
    _gider(db, "Netflix", 200, hesap_id=2)      # kart
    _gider(db, "Sigara", 3600, hesap_id=None)   # belirsiz
    t = calculate_nakit_takvimi(1, db, date(2026, 9, 4))
    assert [k["ad"] for k in t["kalemler"]] == ["Kira"]
    assert [k["ad"] for k in t["karta_yazilacak"]] == ["Netflix"]
    assert [k["ad"] for k in t["hesabi_belirsiz"]] == ["Sigara"]
    assert t["ay_sonu_bakiye"] == D("5000")


def test_KOC_BAGLAMINDA_belirsizlik_YAZILI(db):
    """
    Motorun bildiğini koçun bilmemesi, G3'te ölçülen boşluğun sınıfıdır. Koç
    "hesabı belirsiz şu kadar harcaman var" diyebilmeli — ve SORMALI.
    """
    from app.coach import CoachEngine, LLMResponse

    class _P:
        NAME = "S"; model = "s"; last_used_provider = "s"

        def chat(self, system_prompt, messages, tools):
            _P.gorulen = system_prompt
            return LLMResponse(text="ok", tool_calls=[], usage={"input_tokens": 1,
                               "output_tokens": 1}, provider_used="s", model_name="s")

    _gider(db, "Sigara", 3600, hesap_id=None)
    CoachEngine(provider=_P()).chat(db, 1, "durumu göster", include_cockpit=True)
    assert "HESABI BELİRSİZ" in _P.gorulen.upper(), \
        "koç, hesabı belirsiz gideri hiç görmüyor — varsayım yapmaya devam eder"
