"""
D24 / BUG #240 — "cron çalıştı mı?" sorusunun cevabı 5 işten 3'ü için YOKTU.

`_kayit_basla`/`_kayit_bitir` yalnız iki job'ın GÖVDESİNE elle yazılmıştı; `k2_batch`,
`nightly_trace_cleanup` ve `weekly_smoke_test` hiçbir SchedulerRun satırı açmıyordu.
`/api/ops/scheduler` iş adlarını SchedulerRun tablosundan türettiği için bu üç işi HİÇ
listeleyemiyordu — yani KVKK'da kullanıcıya söz verilen 90-gün saklama işi haftalarca
ölü kalsa kimse göremezdi (taahhüt sessizce ihlal edilir).

Kilitlenen sözleşme (kapsam tabanı assert'li — L11):
1. Planlı işlerin TEK KAYNAĞI `PLANLI_ISLER`; APScheduler'a giden liste birebir odur
   (yeni iş elle `add_job` ile eklenip kayıt dışı kalamaz).
2. Her planlı iş, gövdesine tek satır yazılmasa bile çalışma kaydı bırakır (sarmalayıcı
   yapısaldır — yazarın disiplinine bağlı değil).
3. Patlayan iş `ok=False` ile kapanır; sessizce kaybolmaz.
4. Saklama işi KAÇ SATIR sildiğini kaydeder — KVKK taahhüdü doğrulanabilir olur.
5. Uç, HİÇ çalışmamış planlı işi de listeler ve gecikmişi işaretler (boş liste "her şey
   yolunda" sanılmasın).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.scheduler as sched
from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (Base, User, SchedulerRun, ReasoningTrace, OperationName,
                        Account, AccountType)


@pytest.fixture
def Session():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)


@pytest.fixture
def db(Session, monkeypatch):
    s = Session()
    s.add(User(name="operator"))
    s.commit()
    monkeypatch.setattr(sched, "SessionLocal", Session)
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.query(User).first()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _dis_dunyayi_sustur(monkeypatch, db):
    """İşlerin dış dünyaya uzanan tek tük çağrılarını sabitle (ağ/LLM yok)."""
    import app.price_providers as price_mod
    import app.services.smoke_tests as smoke_mod
    # BUG #248 (D37): fiyat işi artık "hiçbir hesabı güncelleyemedim" durumunu BAŞARISIZ
    # sayıyor. Bu yardımcı "dış dünya sussun, işler temiz koşsun" demek istediği için
    # sağlayıcı GEÇERLİ bir fiyat döndürür (kesinti senaryosu kendi testinde ölçülür).
    monkeypatch.setattr(price_mod, "fetch_for_account", lambda acc: (12.34, "test"))
    monkeypatch.setattr(smoke_mod, "run_all_smoke_tests",
                        lambda: [{"api": "evds", "ok": True, "detail": "200"}])
    monkeypatch.setattr(smoke_mod, "capture_smoke_failures", lambda results: 0)
    u = db.query(User).first()
    db.add(Account(user_id=u.id, name="Fon", account_type=AccountType.investment,
                   balance=100.0, fund_code="ABC"))
    db.commit()


# ---------------------------------------------------------------- 1. kapsam tabanı

def test_planli_is_listesi_apscheduler_ile_birebir():
    """Tek kaynak kilidi: APScheduler'a giden her iş PLANLI_ISLER'den gelir.

    Aksi halde yarın eklenen bir job doğrudan add_job ile geçer ve D24 aynen tekrarlar."""
    assert len(sched.PLANLI_ISLER) >= 5, "kapsam tabanı düştü — iş listesi daraldı"
    beklenen = {p.ad for p in sched.PLANLI_ISLER}
    assert beklenen >= {"fetch_investment_prices", "nightly_batch", "k2_batch",
                        "nightly_trace_cleanup", "weekly_smoke_test"}
    async def _kos():   # AsyncIOScheduler çalışan bir event loop ister
        try:
            s = sched.start_scheduler()
            assert {j.id for j in s.get_jobs()} == beklenen
        finally:
            sched.shutdown_scheduler()

    asyncio.run(_kos())


def test_her_planli_is_kayit_sarmalayicisindan_gecer():
    """Yapısal kilit: kayıt işin gövdesine elle yazılmaz, sarmalayıcıdan gelir."""
    for plan in sched.PLANLI_ISLER:
        assert getattr(plan.fonksiyon, "_izlenen_is_adi", None) == plan.ad, (
            f"{plan.ad} izleme sarmalayıcısı olmadan planlanmış — çalışması görünmez")


# ---------------------------------------------------------------- 2. davranış

@pytest.mark.parametrize("is_adi", ["fetch_investment_prices", "nightly_batch", "k2_batch",
                                    "nightly_trace_cleanup", "weekly_smoke_test"])
def test_her_planli_is_calisma_kaydi_birakir(is_adi, db, monkeypatch):
    _dis_dunyayi_sustur(monkeypatch, db)
    plan = next(p for p in sched.PLANLI_ISLER if p.ad == is_adi)

    asyncio.run(plan.fonksiyon())

    kayit = (db.query(SchedulerRun).filter(SchedulerRun.job_name == is_adi)
             .order_by(SchedulerRun.id.desc()).first())
    assert kayit is not None, f"{is_adi} çalıştı ama hiçbir kayıt bırakmadı"
    assert kayit.finished_at is not None, f"{is_adi} kaydı hiç kapanmadı"
    assert kayit.ok is True


def test_patlayan_is_basarisiz_olarak_kapanir(db, monkeypatch):
    """Sessiz ölüm yok: iş patlarsa kayıt ok=False ile kapanır."""
    import app.services.smoke_tests as smoke_mod

    def _patla():
        raise RuntimeError("smoke boom")

    monkeypatch.setattr(smoke_mod, "run_all_smoke_tests", _patla)
    asyncio.run(sched.weekly_smoke_test_job())  # exception dışarı sızmaz

    kayit = (db.query(SchedulerRun)
             .filter(SchedulerRun.job_name == "weekly_smoke_test").first())
    assert kayit is not None and kayit.ok is False
    assert "RuntimeError" in (kayit.detail or "")


def test_saklama_isi_silinen_satir_sayisini_kaydeder(db):
    """KVKK 90-gün taahhüdü ancak SAYIYLA doğrulanabilir olur."""
    u = db.query(User).first()
    db.add(ReasoningTrace(user_id=u.id, trace_id="eski", step_index=0,
                          operation_name=OperationName.LLM_CALL,
                          created_at=datetime.utcnow() - timedelta(days=120)))
    db.commit()

    asyncio.run(sched.nightly_trace_cleanup_job())

    kayit = (db.query(SchedulerRun)
             .filter(SchedulerRun.job_name == "nightly_trace_cleanup").first())
    assert kayit is not None and kayit.ok is True
    assert "1" in (kayit.detail or ""), f"silinen satır sayısı kayıtta yok: {kayit.detail}"


# ---------------------------------------------------------------- 3. görünürlük ucu

def test_ops_ucu_hic_calismamis_planli_isi_de_listeler(client, db):
    """Uç iş adlarını tablodan türetirse, HİÇ çalışmamış (= ölü) iş görünmez olur —
    tam olarak görülmesi gereken durum."""
    r = client.get("/api/ops/scheduler")
    assert r.status_code == 200
    isler = {i["job_name"]: i for i in r.json()["isler"]}
    for plan in (*sched.PLANLI_ISLER, *sched.DIS_PLANLI_ISLER):
        assert plan.ad in isler, f"{plan.ad} planlı ama uçta görünmüyor"
        assert isler[plan.ad]["hic_calismadi"] is True
        assert isler[plan.ad]["son_calisma"] is None


def test_gecikmis_is_isaretlenir(client, db):
    """Kayıt var ama bayat: günlük iş 3 gündür koşmadıysa uç bunu SÖYLEMELİ."""
    db.add(SchedulerRun(job_name="nightly_batch",
                        started_at=datetime.utcnow() - timedelta(days=3),
                        finished_at=datetime.utcnow() - timedelta(days=3),
                        ok=True, detail="1 kullanici"))
    db.commit()
    isler = {i["job_name"]: i for i in client.get("/api/ops/scheduler").json()["isler"]}
    assert isler["nightly_batch"]["gecikti"] is True
    assert isler["nightly_batch"]["hic_calismadi"] is False
    # taze koşan iş gecikmiş sayılmaz
    db.add(SchedulerRun(job_name="k2_batch", started_at=datetime.utcnow(),
                        finished_at=datetime.utcnow(), ok=True))
    db.commit()
    isler = {i["job_name"]: i for i in client.get("/api/ops/scheduler").json()["isler"]}
    assert isler["k2_batch"]["gecikti"] is False


def test_kayit_tutulmayan_is_kalmadi_ozeti(client, db, monkeypatch):
    """Uç, operatörün tek bakışta karar verebileceği özet döner."""
    _dis_dunyayi_sustur(monkeypatch, db)
    for plan in sched.PLANLI_ISLER:
        asyncio.run(plan.fonksiyon())
    for dis in sched.DIS_PLANLI_ISLER:   # dış işin kaydını işin kendisi yazar
        db.add(SchedulerRun(job_name=dis.ad, started_at=datetime.utcnow(),
                            finished_at=datetime.utcnow(), ok=True, detail="ornek"))
    db.commit()
    body = client.get("/api/ops/scheduler").json()
    assert body["hic_calisma_yok"] is False
    assert body["sorunlu_isler"] == []
    assert len(body["isler"]) == len(sched.PLANLI_ISLER) + len(sched.DIS_PLANLI_ISLER)


# ---------------------------------------------------------------- 4. sınıf taraması (L11)

def test_dis_planli_is_kaydini_kendisi_yazar():
    """Yedek de aynı sınıftaydı: çıkış kodu YALNIZ konteyner log'una düşüyordu.

    Yedek beta verisinin tek kopyası — sessizce ölmesi cron'un ölmesinden ağır. Kaydı
    işin kendisi yazmalı; hem başarı hem BAŞARISIZLIK yolunda (başarısızlık yolu
    kaydetmezse "hiç koşmadı" ile "koştu ve patladı" ayırt edilemez)."""
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent
    for dis in sched.DIS_PLANLI_ISLER:
        kaynak = (kok / dis.yazan).read_text(encoding="utf-8")
        assert "scheduler_runs" in kaynak, f"{dis.yazan} çalışma kaydı yazmıyor"
        assert f"'{dis.ad}'" in kaynak, f"{dis.yazan} kaydı {dis.ad} adıyla yazmıyor"
        assert "kayit false" in kaynak, f"{dis.yazan} başarısızlığı kaydetmiyor"
        assert "kayit true" in kaynak, f"{dis.yazan} başarıyı kaydetmiyor"
        # İzleme işi düşürmemeli: kayıt hatası yutulur (BUG #203 sözleşmesi).
        assert "|| echo" in kaynak, f"{dis.yazan} kayıt hatasında yedeği düşürebilir"


def test_canli_kapi_dolu_listeyi_calisma_sanmaz():
    """BUG #240'ın kendi yarattığı tuzak: uç artık koşmamış işleri de listelediği için
    `bool(isler)` ile "cron çalıştı" ölçülemez — kapı kendini yeşile boyardı."""
    import inspect
    from scripts import live_gate
    src = inspect.getsource(live_gate.kosla)
    assert "hic_calisma_yok" in src, "canlı kapı çalışma varlığını dolu listeden çıkarıyor"
    assert "hic_calismadi" in src and "gecikti" in src, (
        "canlı kapı hiç koşmayan/geciken işi raporlamıyor")


# ---------------------------------------------------------------- 5. BAŞARI SEMANTİĞİ (BUG #248 / D37)

def test_fiyat_isi_hicbir_hesabi_guncelleyemediginde_basarisiz_kaydeder(db, monkeypatch):
    """"İş çökmedi" ile "iş işini yaptı" aynı şey değildir.

    Sağlayıcıların HEPSİ çöktüğünde iş eskiden `ok=True` kaydediyordu → `/api/ops/scheduler`
    "son başarılı: bu sabah" der, `sorunlu_isler`'e düşmez; kesinti operatörden haftalarca
    gizlenir ve koç bayat fiyatla konuşur (BUG #239'un tam olarak beslendiği durum)."""
    import asyncio
    from app.models import Account, AccountType

    db.add(Account(user_id=1, name="TLY Fonu", account_type=AccountType.investment,
                   balance=1000, fund_code="TLY"))
    db.commit()

    monkeypatch.setattr("app.price_providers.fetch_for_account", lambda acc: None)  # sağlayıcı çökük

    asyncio.run(sched.fetch_investment_prices_job())   # sarmalayıcı yutar, KAYDA yazar

    kayit = (db.query(SchedulerRun).filter(SchedulerRun.job_name == "fetch_investment_prices")
             .order_by(SchedulerRun.id.desc()).first())
    assert kayit is not None and kayit.ok is False, (
        "Hiçbir hesabı güncelleyemeyen fiyat işi kendini BAŞARILI kaydediyor — "
        "kesinti operatörden gizlenir"
    )
    assert "0/1" in (kayit.detail or ""), f"kayıt detayı ölçüyü taşımıyor: {kayit.detail!r}"


def test_fiyat_isi_hic_hesap_yoksa_basarilidir(db, monkeypatch):
    """L6: kapı ürünü kıramaz — yatırım hesabı olmayan kullanıcıda 0/0 meşru başarıdır."""
    import asyncio
    sonuc = asyncio.run(sched.fetch_investment_prices_job())
    assert "0/0" in sonuc
