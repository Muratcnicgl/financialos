"""
KAÇIRILAN GECE İŞLERİ TELAFİ KAPISI — BUG #302.

ÖLÇÜLEN DEFEKT: `misfire_grace_time=3600` bir işi yalnız **1 saat** gecikmeye kadar
kurtarır; daha fazlası sessizce atlanır ve o iş o gün bir daha koşmaz. 7/24 açık bir
sunucuda bu makul bir varsayımdır — ama kapalı beta **kişisel bir Windows makinesinde**
koşuyor ve o makine her gece açık kalmaz. Gece 02:45–04:00 penceresi uykuda geçtiğinde:
  · yatırım fiyatları güncellenmiyor → kullanıcı bayat fiyata dayanan bir net değer görüyor
  · gece batch'i (uyarılar, periyodik hesaplar) atlanıyor
  · iz temizliği koşmuyor → 90 günlük saklama sözü kendiliğinden tutulmuyor (KVKK)

Canlı ölçüm (11 Ağu): `scheduler_runs`'ta gerçek gece işlerinden **hiçbirinin** kaydı
yoktu; tablodaki tek ad test kökenli `weekly_smoke_test`ti.

Veri zaten vardı, EYLEM yoktu: `beklenen_periyot_saat` tanımlı ve `/api/ops/scheduler` işi
"gecikti" diye işaretliyordu — ama işaretlemek koşturmaz. **L61: bir gecikmeyi ÖLÇEN
sistem, onu TELAFİ eden sistem değildir; ölçüm bakan biri olmadıkça durumu değiştirmez.**

Sözleşme:
  1. Beklenen periyodunu aşmış iş açılışta koşar.
  2. Hiç koşmamış iş de koşar (yeni kurulum güncel başlasın).
  3. GÜNCEL iş koşmaz — telafi, her açılışta her işi tetikleyen bir kaçak olmamalı.
  4. Yalnız BAŞARILI koşum "koştu" sayılır; başarısız deneme işi güncel yapmaz.
  5. Bir iş patlarsa diğerleri koşmaya devam eder.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.scheduler as sched
from app.models import Base, SchedulerRun


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    s = Session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def sahte_isler(monkeypatch, db):
    """PLANLI_ISLER'i ölçülebilir sahte işlerle değiştirir; DB oturumunu teste bağlar."""
    kosanlar: list[str] = []

    def _yap(ad: str, patlasin: bool = False):
        async def _is():
            kosanlar.append(ad)
            if patlasin:
                raise RuntimeError(f"{ad} patladi")
            return "ok"
        return sched.PlanliIs(ad, _is, {"hour": 3}, 24.0)

    from contextlib import contextmanager

    @contextmanager
    def _oturum():
        yield db

    monkeypatch.setattr(sched, "_db_session", _oturum)
    return kosanlar, _yap


def _kayit(db, ad: str, saat_once: float, ok: bool = True):
    an = datetime.utcnow() - timedelta(hours=saat_once)
    db.add(SchedulerRun(job_name=ad, started_at=an, finished_at=an, ok=ok, detail=""))
    db.commit()


def test_gecikmis_is_telafi_edilir(db, sahte_isler, monkeypatch):
    """KÖK DEFEKT: 30 saat önce koşmuş günlük iş (periyot 24s) şimdi koşmalı."""
    kosanlar, yap = sahte_isler
    monkeypatch.setattr(sched, "PLANLI_ISLER", (yap("gece_isi"),))
    _kayit(db, "gece_isi", saat_once=30)

    asyncio.run(sched.kacirilan_isleri_telafi_et())
    assert kosanlar == ["gece_isi"], (
        "BUG #302: gecikmiş gece işi telafi edilmedi — makine o saatte kapalıysa iş "
        "o gün hiç koşmaz (fiyat bayat kalır, iz temizliği yapılmaz)."
    )


def test_guncel_is_tekrar_kosmaz(db, sahte_isler, monkeypatch):
    """Telafi her açılışta her işi tetikleyen bir kaçak OLMAMALI."""
    kosanlar, yap = sahte_isler
    monkeypatch.setattr(sched, "PLANLI_ISLER", (yap("gece_isi"),))
    _kayit(db, "gece_isi", saat_once=2)     # 2 saat önce koşmuş, periyot 24s

    asyncio.run(sched.kacirilan_isleri_telafi_et())
    assert kosanlar == [], "güncel iş gereksiz yere tekrar koşturuldu"


def test_hic_kosmamis_is_kosar(db, sahte_isler, monkeypatch):
    """Yeni kurulum güncel başlamalı: kaydı olmayan iş bir kez koşar."""
    kosanlar, yap = sahte_isler
    monkeypatch.setattr(sched, "PLANLI_ISLER", (yap("yeni_is"),))

    asyncio.run(sched.kacirilan_isleri_telafi_et())
    assert kosanlar == ["yeni_is"]


def test_basarisiz_kosum_isi_guncel_saymaz(db, sahte_isler, monkeypatch):
    """`ok=False` bir deneme işi 'koşmuş' yapmaz — yoksa sürekli patlayan iş sessizce ölür."""
    kosanlar, yap = sahte_isler
    monkeypatch.setattr(sched, "PLANLI_ISLER", (yap("kirik_is"),))
    _kayit(db, "kirik_is", saat_once=1, ok=False)   # 1 saat önce ama BAŞARISIZ

    asyncio.run(sched.kacirilan_isleri_telafi_et())
    assert kosanlar == ["kirik_is"], "başarısız deneme işi güncel saymamalı"


def test_patlayan_is_digerlerini_dusurmez(db, sahte_isler, monkeypatch):
    """Telafi bir zincirdir; ilk halka kopunca kalanı da kaybedilmemeli."""
    kosanlar, yap = sahte_isler
    monkeypatch.setattr(sched, "PLANLI_ISLER",
                        (yap("patlayan", patlasin=True), yap("saglam")))

    ozet = asyncio.run(sched.kacirilan_isleri_telafi_et())
    assert "saglam" in kosanlar, "patlayan iş sonrakini engelledi"
    assert "patlayan" in kosanlar, "patlayan iş hiç denenmedi"
    assert "saglam" in ozet


def test_lifespan_telafiyi_baslatir_ama_beklemez():
    """Açılış telafiyi BEKLEMEMELİ: kullanıcı gece işinin bitmesini beklememeli."""
    kaynak = (__import__("pathlib").Path(__file__).resolve().parent.parent
              / "app" / "main.py").read_text(encoding="utf-8")
    assert "kacirilan_isleri_telafi_et" in kaynak, "telafi lifespan'e bağlanmamış"
    assert "asyncio.create_task(kacirilan_isleri_telafi_et())" in kaynak, (
        "telafi `await` ile çağrılıyor olabilir — açılışı bloklar (uygulama geç açılır)"
    )
