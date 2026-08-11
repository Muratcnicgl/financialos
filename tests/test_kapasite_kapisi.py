"""
P5.5 — BUG #263: KAPASİTE SINIRLARI (eşzamanlı kullanıcı / DB havuzu / LLM eşzamanlılığı).

ÖLÇÜLEN GERÇEKLİK (iddia değil):
  - `app/routers/*.py` içindeki 114 ucun **tamamı** senkron (`def`) → her istek anyio iş
    parçacığı havuzunda koşar (varsayılan 40/process) ve `Depends(get_db)` oturumu isteğin
    SONUNA kadar bağlantıyı tutar.
  - Prod havuzu process başına 15 bağlantı (`DB_POOL_SIZE 5 + DB_MAX_OVERFLOW 10`).
  - Koç isteği iki LLM çağrısı yapar; bu 10-40 sn boyunca bağlantı elde tutulur.
  → 15 eşzamanlı koç isteği havuzu kilitler; 16. istek `pool_timeout` bekler ve **500** alır;
    `/api/ready` de asılır → Docker HEALTHCHECK zaman aşımı → konteyner yeniden başlar.

`app/database.py`'deki eski kapasite muhakemesi yalnız Postgres `max_connections` tarafına
bakıyordu; uygulamanın kendi içinde havuzun daha ÖNCE tükeneceği hiç hesaba katılmamıştı.

KİLİTLENEN SÖZLEŞME:
  1. Değişmez: `yavaş yol tavanları + hızlı-yol rezervi ≤ DB havuz kapasitesi`
     ve `iş parçacığı havuzu ≤ DB havuz kapasitesi`. İhlal production'da FAIL-FAST.
  2. Yavaş yol tavanı dolunca istek **beklemez**: 503 + `Retry-After` (beklemek iş
     parçacığını VE DB bağlantısını tutmaya devam etmektir).
  3. Reddedilen koç isteği kullanıcının günlük hakkını YAKMAZ.
  4. 503 bir arıza değildir: `error_logs`'a "beklenmedik hata" olarak YAZILMAZ.
  5. Yavaş yollar doluyken HIZLI uçlar çalışmaya devam eder (ürünün "yük altında açık
     kalır" sözü budur).
  6. `/api/ready` havuz doygunken **hızlı** 503 döner, `pool_timeout` kadar asılmaz.
"""
from __future__ import annotations

import threading
import time

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import capacity as kapasite
from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, ApiCallLog, ErrorLog
import app.routers.coach as coach_router


# ============================================================================
# A) YAPILANDIRMA DEĞİŞMEZİ
# ============================================================================

@pytest.fixture
def postgres_gibi(monkeypatch):
    """Kapasite muhakemesi prod dialect'i (PostgreSQL) içindir; onu simüle et."""
    import app.database as _db
    monkeypatch.setattr(_db, "IS_POSTGRES", True, raising=False)
    for ad in ("DB_POOL_SIZE", "DB_MAX_OVERFLOW", "LLM_MAX_CONCURRENCY",
               "DIS_SERVIS_MAX_CONCURRENCY", "EPOSTA_MAX_CONCURRENCY",
               "THREADPOOL_TOKENS", "MIN_HIZLI_SLOT"):
        monkeypatch.delenv(ad, raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


def test_varsayilan_yapilandirma_tutarli(postgres_gibi):
    """Kutudan çıktığı hâliyle değişmez sağlanmalı — aksi halde kapı ilk günden kırmızı olur."""
    assert kapasite.db_havuz_kapasitesi() == 15
    assert kapasite.ihlaller() == [], kapasite.ihlaller()


def test_yavas_tavanlar_havuzu_yiyemez(postgres_gibi, monkeypatch):
    """LLM tavanı havuzu doldururcasına açılırsa hızlı uçlara yer kalmaz → ihlal."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "20")
    sorunlar = kapasite.ihlaller()
    assert sorunlar, "Tavan havuzdan büyükken ihlal bildirilmedi"
    assert "hızlı-yol rezervi" in sorunlar[0]


def test_is_parcacigi_havuzu_db_havuzunu_asamaz(postgres_gibi, monkeypatch):
    """Asıl kök neden: eşzamanlılık (40) > bağlantı (15). Kapı bunu görmeli."""
    monkeypatch.setenv("THREADPOOL_TOKENS", "40")
    sorunlar = kapasite.ihlaller()
    assert any("iş parçacığı havuzu" in s for s in sorunlar), sorunlar


def test_production_tutarsizlikta_ACILMAZ(postgres_gibi, monkeypatch):
    """Yanlış yapılandırma canlıda ancak ilk yükte (kullanıcı 500 görünce) anlaşılırdı."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "20")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="Kapasite yapılandırması tutarsız"):
        kapasite.dogrula()


def test_dev_tutarsizlikta_KILITLENMEZ(postgres_gibi, monkeypatch):
    """L6: kapı ürünü kırmamalı — geliştirme ortamı yalnız uyarı alır."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "20")
    kapasite.dogrula()   # raise etmemeli


def test_sqlite_dev_muhakemeye_tabi_degil(monkeypatch):
    """SQLite'ta darboğaz bağlantı sayısı değil yazma kilididir; ölçüt uydurmayız."""
    import app.database as _db
    monkeypatch.setattr(_db, "IS_POSTGRES", False, raising=False)
    assert kapasite.db_havuz_kapasitesi() is None
    assert kapasite.ihlaller() == []
    assert kapasite.threadpool_tokens() is None   # anyio varsayılanına dokunulmaz


def test_uygula_is_parcacigi_havuzunu_GERCEKTEN_degistirir(postgres_gibi):
    """`uygula()` yalnız log basmasın — anyio limiter'ı ölçülerek doğrulanır."""
    import anyio
    from anyio.from_thread import start_blocking_portal

    with start_blocking_portal() as portal:
        onceki = portal.call(lambda: anyio.to_thread.current_default_thread_limiter().total_tokens)
        uygulanan = portal.call(kapasite.uygula)
        sonraki = portal.call(lambda: anyio.to_thread.current_default_thread_limiter().total_tokens)
        portal.call(lambda: setattr(anyio.to_thread.current_default_thread_limiter(),
                                    "total_tokens", onceki))
    assert uygulanan == 15
    assert sonraki == 15, f"limiter değişmedi (önce={onceki}, sonra={sonraki})"


# ============================================================================
# B) SEMAFOR DAVRANIŞI
# ============================================================================

def test_tavan_dolunca_BEKLEMEZ_reddeder(monkeypatch):
    """Beklemek iş parçacığını + DB bağlantısını tutmaya devam etmektir → reddet."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    t0 = time.time()
    with kapasite.yavas_yol(kapasite.LLM):
        with pytest.raises(kapasite.KapasiteDolu):
            with kapasite.yavas_yol(kapasite.LLM):
                pass
    assert time.time() - t0 < 1.0, "Tavan dolunca beklendi (bloklayıcı acquire)"


def test_slot_istisnada_da_geri_verilir(monkeypatch):
    """Sızdıran semafor, ilk hatadan sonra ucu kalıcı olarak kapatırdı."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    with pytest.raises(ValueError):
        with kapasite.yavas_yol(kapasite.LLM):
            raise ValueError("patla")
    with kapasite.yavas_yol(kapasite.LLM):   # slot geri gelmiş olmalı
        pass


def test_yollar_birbirini_kilitlemez(monkeypatch):
    """LLM tavanı dolu diye döviz kuru çekilememesi kabul edilemez."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("DIS_SERVIS_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("EPOSTA_MAX_CONCURRENCY", "1")
    with kapasite.yavas_yol(kapasite.LLM):
        with kapasite.yavas_yol(kapasite.DIS_SERVIS):
            # EVDS/OAuth doluyken şifre-sıfırlama e-postası HÂLÂ gidebilmeli: kur bilgisi
            # kozmetiktir, hesabına giremeyen kullanıcı kilitlenmiştir.
            with kapasite.yavas_yol(kapasite.EPOSTA):
                pass


# ============================================================================
# B2) E-POSTA YOLU — tek bekleme istisnası (BUG #263 sınıf taraması)
# ============================================================================

def test_yalniz_eposta_bekler_digerleri_ANINDA_reddeder():
    """İstisna tek yerde tanımlı olmalı; yayılırsa "beklemeyen tavan" kuralı erir."""
    assert kapasite.bekleme(kapasite.EPOSTA) > 0
    assert kapasite.bekleme(kapasite.LLM) == 0
    assert kapasite.bekleme(kapasite.DIS_SERVIS) == 0


@pytest.fixture
def smtp_yapilandirildi(monkeypatch):
    for ad, deger in (("SMTP_HOST", "smtp.test"), ("SMTP_PORT", "587"),
                      ("SMTP_USER", "u"), ("SMTP_PASS", "p"),
                      ("SMTP_FROM", "no-reply@test")):
        monkeypatch.setenv(ad, deger)


def test_smtp_tavani_dolunca_False_doner_PATLAMAZ(smtp_yapilandirildi, monkeypatch):
    """Sözleşme korunur: `send_email` tavan doluyken de True/False döner, istisna sızdırmaz.

    Önemi: bu fonksiyon `BackgroundTasks` içinden de çağrılır. Oradan sızan bir istisna
    kullanıcıya ulaşmaz, sessizce log'a düşer — ve kayıt akışında zaten OLUŞMUŞ bir hesabı
    503 ile başarısız göstermek yanlış olurdu.
    """
    import app.services.email as eposta

    monkeypatch.setenv("EPOSTA_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("EPOSTA_BEKLEME_SANIYE", "0.2")   # kapı hızlı koşsun

    def _smtp_kullanilmamali(*a, **k):
        raise AssertionError("Tavan doluyken SMTP bağlantısı açıldı")
    monkeypatch.setattr(eposta.smtplib, "SMTP", _smtp_kullanilmamali)

    with kapasite.yavas_yol(kapasite.EPOSTA):        # tek slot işgal edildi
        t0 = time.time()
        sonuc = eposta.send_email("a@b.com", "k", "metin", "<p>metin</p>")
        sure = time.time() - t0

    assert sonuc is False
    assert 0.15 < sure < 3.0, f"bekleme süresi beklenen aralıkta değil: {sure:.2f} sn"


def test_eposta_slotu_bosalinca_gonderim_SURER(smtp_yapilandirildi, monkeypatch):
    """Tavan bir kerelik kapı değildir: slot boşalınca sonraki e-posta gitmeli."""
    import app.services.email as eposta

    monkeypatch.setenv("EPOSTA_MAX_CONCURRENCY", "1")
    gonderilenler: list = []

    class _SahteSMTP:
        def __init__(self, host, port, timeout=None):
            gonderilenler.append(host)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def ehlo(self): pass
        def starttls(self, context=None): pass
        def login(self, u, p): pass
        def sendmail(self, f, t, m): pass

    monkeypatch.setattr(eposta.smtplib, "SMTP", _SahteSMTP)
    assert eposta.send_email("a@b.com", "k", "m", "<p>m</p>") is True
    assert eposta.send_email("c@d.com", "k", "m", "<p>m</p>") is True
    assert len(gonderilenler) == 2


# ============================================================================
# C) UÇTAN UCA DAVRANIŞ (koç + hızlı uçlar)
# ============================================================================

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-kapasite-0123456789abcdef")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "0")   # kota kapısı bu dosyanın konusu değil


@pytest.fixture
def oturum_fabrikasi(tmp_path):
    """Dosya tabanlı DB: istekler gerçekten paralel koşuyor (Session thread-safe değil)."""
    eng = create_engine(f"sqlite:///{tmp_path / 'kapasite.db'}",
                        connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(eng)
    fabrika = sessionmaker(bind=eng)
    s = fabrika()
    s.add(User(name="a"))
    s.commit()
    s.close()
    yield fabrika
    eng.dispose()


@pytest.fixture
def db(oturum_fabrikasi):
    s = oturum_fabrikasi()
    yield s
    s.close()


@pytest.fixture
def client(oturum_fabrikasi):
    def _istek_oturumu():
        s = oturum_fabrikasi()
        try:
            yield s
        finally:
            s.close()

    def _istek_kullanicisi(d: Session = Depends(get_db)):
        return d.query(User).first()

    app.dependency_overrides[get_db] = _istek_oturumu
    app.dependency_overrides[get_current_user] = _istek_kullanicisi
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


class _AskidaMotor:
    """LLM çağrısını `devam` verilene kadar askıda tutar — slot dolu kalsın."""
    provider_name = "FakeProvider"
    model = "fake-model"

    def __init__(self) -> None:
        self.girdi = threading.Event()
        self.devam = threading.Event()

    def chat(self, *a, **k):
        self.girdi.set()
        self.devam.wait(timeout=10)
        return {"reply": "ok", "proposed_actions": [], "cockpit_snapshot": None,
                "coach_memory_id": None}


@pytest.fixture
def askida_motor(monkeypatch):
    m = _AskidaMotor()
    monkeypatch.setattr(coach_router, "_get_engine", lambda: m)
    yield m
    m.devam.set()


def _koc_iste(client, kutu: list, anahtar: str):
    r = client.post("/api/coach/chat", json={"message": "merhaba"})
    kutu.append((anahtar, r.status_code, r.headers.get("Retry-After"), r.json()))


def test_llm_tavani_dolunca_NAZIK_503(client, askida_motor, monkeypatch):
    """Tavan 1: ilk istek LLM'in içindeyken gelen ikinci istek 503 + Retry-After almalı."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    sonuc: list = []
    t = threading.Thread(target=_koc_iste, args=(client, sonuc, "A"))
    t.start()
    assert askida_motor.girdi.wait(timeout=10), "İlk istek LLM'e hiç ulaşmadı"

    r = client.post("/api/coach/chat", json={"message": "ikinci"})
    assert r.status_code == 503, r.text[:300]
    assert r.headers.get("Retry-After"), "Retry-After başlığı yok (istemci ne zaman denesin?)"
    assert "yoğun" in r.json()["detail"].lower()

    askida_motor.devam.set()
    t.join(timeout=15)
    assert sonuc and sonuc[0][1] == 200, sonuc


def test_reddedilen_istek_gunluk_hakki_YAKMAZ(client, db, askida_motor, monkeypatch):
    """Slot kota rezervasyonundan ÖNCE alınır: 503 alan kullanıcı hakkını kaybetmemeli."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    sonuc: list = []
    t = threading.Thread(target=_koc_iste, args=(client, sonuc, "A"))
    t.start()
    assert askida_motor.girdi.wait(timeout=10)

    once = db.query(ApiCallLog).count()
    assert client.post("/api/coach/chat", json={"message": "ikinci"}).status_code == 503
    db.expire_all()
    assert db.query(ApiCallLog).count() == once, "Reddedilen istek kota sayacına yazıldı"

    askida_motor.devam.set()
    t.join(timeout=15)


def test_503_beklenmedik_hata_olarak_KAYDEDILMEZ(client, db, askida_motor, monkeypatch):
    """Sırt basıncı arıza değildir; error_logs'a düşerse gerçek arızalar gürültüde kaybolur."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    sonuc: list = []
    t = threading.Thread(target=_koc_iste, args=(client, sonuc, "A"))
    t.start()
    assert askida_motor.girdi.wait(timeout=10)

    once = db.query(ErrorLog).count()
    assert client.post("/api/coach/chat", json={"message": "ikinci"}).status_code == 503
    db.expire_all()
    assert db.query(ErrorLog).count() == once, "503 sırt basıncı hata kaydı üretti"

    askida_motor.devam.set()
    t.join(timeout=15)


def test_yavas_yol_doluyken_HIZLI_uclar_calisir(client, askida_motor, monkeypatch):
    """Ürünün "yük altında açık kalır" sözü: koç meşgulken paneller ayakta olmalı."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    sonuc: list = []
    t = threading.Thread(target=_koc_iste, args=(client, sonuc, "A"))
    t.start()
    assert askida_motor.girdi.wait(timeout=10)

    t0 = time.time()
    assert client.get("/api/ready").status_code == 200
    assert client.get("/api/cockpit").status_code == 200
    assert time.time() - t0 < 5, "Hızlı uçlar yavaş yol yüzünden yavaşladı"

    askida_motor.devam.set()
    t.join(timeout=15)


# ============================================================================
# D) /api/ready — HAVUZ DOYGUNKEN HIZLI 503
# ============================================================================

def test_ready_havuz_doygunken_HIZLI_503(client, monkeypatch):
    """Eskiden `SELECT 1` `pool_timeout` (30 sn) boyunca asılırdı → HEALTHCHECK zaman
    aşımı → konteyner yeniden başlar: geçici yük dalgası KALICI kesintiye dönerdi."""
    import app.routers.meta as meta_router
    monkeypatch.setattr("app.capacity.havuz_doygun_mu", lambda: True)

    t0 = time.time()
    r = client.get("/api/ready")
    sure = time.time() - t0

    assert r.status_code == 503
    assert r.json()["detail"]["db"] == "havuz_dolu"
    assert sure < 2.0, f"/api/ready havuz doygunken {sure:.1f} sn asıldı"
    assert meta_router is not None   # import kullanıldı (kapı dosyayı gerçekten yüklüyor)


def test_ready_normalde_200(client):
    assert client.get("/api/ready").status_code == 200


# ============================================================================
# E) KAPSAM TABANI — kapı ölçtüğünü ölçüyor mu (L27)
# ============================================================================

def test_kapasite_env_adlari_belgede_yazili():
    """Operatör ayarı bilmiyorsa ayar yok demektir: adlar runbook'ta geçmeli."""
    from pathlib import Path
    kok = Path(__file__).resolve().parents[1]
    metin = ""
    for aday in ("docs/deployment/runbook.md", ".env.prod.example"):
        yol = kok / aday
        if yol.exists():
            metin += yol.read_text(encoding="utf-8")
    assert metin, "Ne runbook ne .env.prod.example bulundu — kapı ölçmüyor"
    for ad in ("LLM_MAX_CONCURRENCY", "DIS_SERVIS_MAX_CONCURRENCY",
               "EPOSTA_MAX_CONCURRENCY", "DB_POOL_TIMEOUT"):
        assert ad in metin, f"{ad} hiçbir operatör belgesinde geçmiyor"


def test_runbook_kucuk_vm_tarifi_degismezi_saglar(postgres_gibi, monkeypatch):
    """Runbook'un küçük-VM tarifi UYGULANABİLİR olmalı — belge kod ile birlikte ölçülür.

    İlk yazımda tarif yalnız havuzu küçültüyordu (`DB_POOL_SIZE=3` + `DB_MAX_OVERFLOW=5`
    = 8) ama tavanlar varsayılanda kalıyordu (3 + 3 + 6 = 12 > 8). Yani belgeyi harfiyen
    uygulayan operatörün konteyneri **hiç açılmazdı** (production'da fail-fast) — ve bunu
    ancak canlı deploy sırasında öğrenirdi. Bu kapı tarifi belgeden OKUYUP koşturur:
    ikisi ayrışırsa süit kırmızıya döner (R3: iddiayı ancak onu ölçen bir koşum kapatır).
    """
    import re
    from pathlib import Path

    yol = Path(__file__).resolve().parents[1] / "docs/deployment/runbook.md"
    metin = yol.read_text(encoding="utf-8")
    blok = re.search(r"### Küçük VM tarifi.*?```sh\n(.*?)```", metin, re.S)
    assert blok, "Runbook'ta küçük-VM tarifi bulunamadı (belge yeniden adlandırıldı mı?)"

    tarif = dict(re.findall(r"^(\w+)=(\d+)", blok.group(1), re.M))
    for ad in ("DB_POOL_SIZE", "DB_MAX_OVERFLOW", "LLM_MAX_CONCURRENCY",
               "DIS_SERVIS_MAX_CONCURRENCY", "EPOSTA_MAX_CONCURRENCY", "MIN_HIZLI_SLOT"):
        assert ad in tarif, f"Tarifte {ad} yok — operatör eksik takımla deploy eder"
        monkeypatch.setenv(ad, tarif[ad])

    assert kapasite.ihlaller() == [], (
        f"Runbook'un küçük-VM tarifi kendi değişmezini ihlal ediyor: {kapasite.ihlaller()}")

    monkeypatch.setenv("ENVIRONMENT", "production")
    kapasite.dogrula()   # tarif ile production'da AÇILABİLMELİ


def test_her_yavas_yol_adinin_tavani_var():
    """Yeni bir yol adı eklenip tavanı unutulursa o yol SESSİZCE sınırsız çalışırdı (L26)."""
    for ad in (kapasite.LLM, kapasite.DIS_SERVIS, kapasite.EPOSTA):
        assert ad in kapasite._VARSAYILAN_TAVAN
        assert kapasite.tavan(ad) >= 1
