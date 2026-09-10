"""
KOÇUN HAFIZASI KULLANICIYA AİTTİR — operatör telemetrisi slot işgal edemez.

ÖLÇÜLEN DEFEKT (10 Eyl 2026, canlı bağlam): `## UZUN VADELI HAFIZA` bloğu koça
"Bu kullanici hakkinda gecmis etkilesimlerden ogrenilen gerceklerdir" diye sunuluyor ve
yalnız **5 slot** taşıyor. O 5 slotun İKİSİNİ, üstelik en yüksek öncelikli ikisini
(sort_priority 10 ve 9) koçun KENDİ telemetrisi işgal ediyordu:
    [MC_REFERENCE_FREQUENCY] "MC8 kurali 6 kez referans verildi (rank 1/3)"
    [QUESTION_TYPOLOGY]      "Dusuk acik soru orani / OARS dengesi"
İkisi de `CoachMemory.role == "assistant"` üzerinden, yani KOÇUN ÇIKTISINDAN hesaplanır;
kullanıcı hakkında hiçbir şey söylemezler. Gerçek kullanıcı gözlemleri (sort_priority 5)
yapısal olarak dışarı itiliyordu — zarar token değil SLOT.

Kayıtlar silinmiyor: operatör/kalite döngüsü onları okumaya devam eder. Değişen tek şey,
koçun kendi bağlamına girmemeleri.

NULL TUZAĞI (ilk denemede ölçüldü ve buraya kilitlendi): `insight_type NOT IN (...)` SQL'de
NULL için NULL döner → tipi boş olan GERÇEK gözlemler de sessizce düşer. İlk yamada tam
olarak bu oldu, 3 gerçek gözlem birden kayboldu. Boş tip açıkça korunmalı.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.coach_insights import OPERATOR_ICGORU_TIPLERI, format_insights_for_prompt
from app.database import Base
from app.models import CoachInsight, User


@pytest.fixture
def db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="kullanici"))
    s.commit()
    yield s
    s.close()


def _icgoru(db, *, tip, baslik, oncelik, icerik="gozlem"):
    db.add(CoachInsight(user_id=1, insight_type=tip, title=baslik, content=icerik,
                        status="active", sort_priority=oncelik, is_active=True))
    db.commit()


def test_operator_telemetrisi_koc_baglamina_GIRMEZ(db):
    """Bildirilen defekt: en yüksek öncelikli iki slot koçun kendi istatistiğiydi."""
    _icgoru(db, tip="mc_reference_frequency", baslik="MC8 sik referans", oncelik=10)
    _icgoru(db, tip="question_typology", baslik="Dusuk acik soru orani", oncelik=9)
    blok = format_insights_for_prompt(db, 1)
    assert "MC8" not in blok
    assert "acik soru orani" not in blok.lower()


def test_KULLANICI_gozlemi_korunur(db):
    """Kapının kendisi çalışıyor mu — hepsini elemek de bir defekt olurdu (ders L28)."""
    _icgoru(db, tip="category_account_preference", baslik="market tercihi", oncelik=5,
            icerik="market harcamasi haftalik tekrar ediyor")
    blok = format_insights_for_prompt(db, 1)
    assert "market harcamasi haftalik" in blok


def test_TIPI_BOS_gozlem_NULL_tuzagina_dusmez(db):
    """`NOT IN` NULL'ı eler; ilk yamada 3 gerçek gözlem böyle kayboldu."""
    _icgoru(db, tip=None, baslik=None, oncelik=5,
            icerik="Kullanici sigaraya zam gelecegi icin 21 paket aldi")
    blok = format_insights_for_prompt(db, 1)
    assert "21 paket" in blok, "tipi boş olan gerçek gözlem elendi (NULL tuzağı geri geldi)"


def test_telemetri_gercek_gozlemi_SLOTTAN_ETMEZ(db):
    """Asıl zarar buydu: 5 slot, ikisini telemetri yiyordu ve önceliği daha yüksekti."""
    _icgoru(db, tip="mc_reference_frequency", baslik="MC8 sik referans", oncelik=10)
    _icgoru(db, tip="question_typology", baslik="OARS dengesi", oncelik=9)
    for i in range(5):
        _icgoru(db, tip=None, baslik=f"gozlem{i}", oncelik=5, icerik=f"kullanici gercegi {i}")
    blok = format_insights_for_prompt(db, 1)
    for i in range(5):
        assert f"kullanici gercegi {i}" in blok, f"gerçek gözlem {i} slottan edildi"


def test_operator_tip_listesi_bos_degil(db):
    """Liste boşalırsa filtre sessizce ölür ve kimse fark etmez."""
    assert set(OPERATOR_ICGORU_TIPLERI) == {"mc_reference_frequency", "question_typology"}
