"""
B3 / BUG #280 — KORELASYON KİMLİĞİ: log ↔ yanıt ↔ ekran AYNI kimliği taşır.

Sorun: kapalı betada davetli "bir şeyler patladı" der. Sistem hatayı KAYDEDİYORDU
(`error_logs`, BUG #195) ama kullanıcının gördüğü olayla kaydı EŞLEŞTİREMİYORDU:
kullanıcıda yalnız "Beklenmedik bir hata oluştu." cümlesi, log'da binlerce satır,
`error_logs`'ta parmak izine göre birleştirilmiş kayıtlar vardı. "Spesifik debug"
isteğinin eksik halkası tam burasıydı.

Kilitlenen sözleşme (tek cümle): **bir isteğin kimliği; log satırında, hata yanıtında ve
kullanıcıya gösterilen ekranda AYNIDIR.**

Bu kapı zincirin her halkasını ayrı ayrı sınar — çünkü bir halka koparsa (örneğin yanıt
kimliği taşır ama log taşımaz) sistem "çalışıyor gibi" görünür ve eksiklik ancak gerçek
bir arıza gününde fark edilir.
"""
from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.correlation import (
    IstekIdFiltresi, gelen_id_temizle, istek_id, istek_id_var, yeni_id,
)
from app.logging_config import JsonFormatter
from app.main import app
from app.dependencies import get_db
from app.models import Base, ErrorLog

BASLIK = "X-Request-Id"


# ── Çökme nasıl tetiklenir: ÜRETİM APP'İNE HİÇ DOKUNMADAN ───────────────────
# İlk yazımda bu dosya `app`'e geçici bir "patlayan uç" ekliyordu (teardown'da siliyordu).
# Tam süitte tek kırmızı olarak çıktı: `pytest-randomly` testleri karıştırdığı için, uç
# KAYITLIYKEN başka bir dosyanın kapısı araya girdi ve OpenAPI'den uç envanteri türeten
# kapı (BUG #217) o ucu gerçek sanıp çağırdı → 500. OpenAPI önbelleğini de temizlemek
# yetmedi; sorun izin süresiydi, izin kendisi değil.
#
# Doğrusu: üretim app'ine HİÇBİR iz bırakmamak. `get_db` bağımlılığı patlatılır — gerçek
# middleware, gerçek hata yakalayıcı ve gerçek yanıt yolu aynen çalışır, ama uygulama
# nesnesinde geriye tek satır kalmaz (BUG #235 dersinin tam uygulaması).
_PATLAYAN_UC = "/api/meta/durum"   # `get_db`'ye bağlı, kimliksiz erişilebilir


def _patlayan_db():
    raise RuntimeError("bilerek patlatildi")


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db, monkeypatch):
    """Sağlıklı istemci: gerçek app, çalışan DB."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-korelasyon-0123456789abcdef")
    app.dependency_overrides[get_db] = lambda: db
    # Hata yakalayıcı kendi session'ını açar (SessionLocal) — testte de aynı belleğe baksın.
    monkeypatch.setattr("app.database.SessionLocal", sessionmaker(bind=db.get_bind()))
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def patlayan_client(db, monkeypatch):
    """Gerçek 500 üreten istemci — `get_db` patlar, üretim app'i değişmez."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-korelasyon-0123456789abcdef")
    app.dependency_overrides[get_db] = _patlayan_db
    monkeypatch.setattr("app.database.SessionLocal", sessionmaker(bind=db.get_bind()))
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════
# 1. Kimlik üretimi ve devralma
# ══════════════════════════════════════════════════════════════════════

def test_uretilen_kimlik_tahmin_edilemez_ve_okunur():
    kimlikler = {yeni_id() for _ in range(200)}
    assert len(kimlikler) == 200, "Kimlikler çakışıyor — rastgelelik yetersiz"
    for k in kimlikler:
        assert len(k) == 8
        # Karışan karakterler (0/O, 1/l/I) elenmiş: kullanıcı telefondan okuyup yazacak.
        assert not set(k) & set("01loIO"), f"Karışabilen karakter üretildi: {k}"


def test_sirali_kimlik_uretilmez():
    """Sayaç/zaman tabanlı kimlik trafik hacmini sızdırır — art arda üretilenler bitişik olmamalı."""
    art_arda = [yeni_id() for _ in range(20)]
    assert len(set(art_arda)) == 20
    assert art_arda != sorted(art_arda), "Kimlikler sıralı görünüyor (tahmin edilebilir)"


@pytest.mark.parametrize("gelen,beklenen", [
    ("abc123", "abc123"),
    ("  abc123  ", "abc123"),
    ("7f3a-9b:1.2_x", "7f3a-9b:1.2_x"),           # vekil biçimleri (Cf-Ray vb.)
    ("", None),
    (None, None),
    ("kotu deger", None),                          # boşluk → log satırı bölünemez
    ("satir\nsonu", None),                         # log enjeksiyonu
    ("x" * 65, None),                              # uzunluk sınırı
    ("<script>", None),
])
def test_vekilden_gelen_kimlik_temizlenir(gelen, beklenen):
    assert gelen_id_temizle(gelen) == beklenen


def test_vekilin_kimligi_DEVRALINIR(client):
    """Kenardaki kaydı kendi kimliğimizle koparmayız — iki ayrı iz üretmek teşhisi böler."""
    r = client.get("/api/health", headers={BASLIK: "vekil-kimligi-1"})
    assert r.headers[BASLIK] == "vekil-kimligi-1"


def test_cf_ray_de_devralinir(client):
    """Cloudflare Tunnel yolunda kimlik `Cf-Ray` ile gelir (B0 seçeneği A)."""
    r = client.get("/api/health", headers={"Cf-Ray": "8a1bc2d3e4f5g6h7"})
    assert r.headers[BASLIK] == "8a1bc2d3e4f5g6h7"


def test_kimlik_yoksa_uretilir(client):
    r = client.get("/api/health")
    assert len(r.headers[BASLIK]) == 8


def test_bozuk_vekil_kimligi_kabul_edilmez(client):
    """Geçersiz başlık sessizce kabul edilmez; kendi kimliğimiz üretilir."""
    r = client.get("/api/health", headers={BASLIK: "bozuk deger"})
    assert r.headers[BASLIK] != "bozuk deger"
    assert len(r.headers[BASLIK]) == 8


def test_her_istek_ayri_kimlik_alir(client):
    a = client.get("/api/health").headers[BASLIK]
    b = client.get("/api/health").headers[BASLIK]
    assert a != b, "İki farklı istek aynı kimliği aldı — bağlam sızıyor"


def test_istek_bittikten_sonra_baglam_sizmaz():
    """İstek bitince kimlik geri alınmalı; yoksa SONRAKİ arka plan işi (cron, açılış)
    bitmiş bir isteğin kimliğiyle loglanır ve teşhis zinciri yanlış yere işaret eder.

    Ölçüm iki kez düzeltildi (mutasyon M6 ikisini de yakaladı):
      1. `TestClient` üzerinden bakmak İŞE YARAMAZ — istek ayrı bir iş parçacığında koşar.
      2. `asyncio.run(...)` da işe yaramaz — Task, bağlamın KOPYASINDA çalışır; içerideki
         `set` dışarı sızmaz, yani reset silinse bile test yeşil kalır.
    Doğrusu: koroutini Task'a sarmadan, BU bağlamda elle sürmek.
    """
    from starlette.responses import PlainTextResponse
    from app.main import _KorelasyonMiddleware

    ara = _KorelasyonMiddleware(app=None)
    sahte_istek = type("Sahte", (), {"headers": {}})()

    async def sahte_sonraki(_):
        return PlainTextResponse("ok")

    assert istek_id() == "-", "Test başlarken bağlam zaten kirli"
    koroutin = ara.dispatch(sahte_istek, sahte_sonraki)
    try:
        koroutin.send(None)          # Task YOK → bağlam bu testinki
    except StopIteration:
        pass
    finally:
        koroutin.close()
    assert istek_id() == "-", "İstek bittikten sonra kimlik bağlamda KALDI (reset yok)"


def test_istek_disinda_kimlik_tire_dir():
    """Kimliksiz bağlamda değer '-' olur; boş string DEĞİL (bilinmeyen ≠ boş, L45 ruhu)."""
    assert istek_id() == "-"


# ══════════════════════════════════════════════════════════════════════
# 2. Zincir: yanıt ↔ log ↔ kalıcı kayıt
# ══════════════════════════════════════════════════════════════════════

def test_hata_yaniti_kimligi_KULLANICIYA_soyler(patlayan_client):
    r = patlayan_client.get(_PATLAYAN_UC)
    assert r.status_code == 500
    govde = r.json()
    kimlik = r.headers[BASLIK]
    assert govde["istek_id"] == kimlik
    assert kimlik in govde["detail"], (
        "Kullanıcının OKUYACAĞI cümlede kimlik yok — davetli 'şu kod çıktı' diyemez"
    )


def test_hata_yaniti_ic_detay_sizdirmaz(client):
    """Kimlik detay DEĞİLDİR: hata metnini/tipini taşımaz (BUG #175 korunur)."""
    r = client.get("/api/__korelasyon_test_patlat")
    metin = json.dumps(r.json(), ensure_ascii=False)
    assert "RuntimeError" not in metin
    assert "bilerek patlatildi" not in metin


def test_kalici_kayit_ayni_kimligi_tasir(patlayan_client, db):
    r = patlayan_client.get(_PATLAYAN_UC)
    kimlik = r.headers[BASLIK]
    kayit = db.query(ErrorLog).first()
    assert kayit is not None, "Hata kaydedilmedi"
    assert kayit.last_istek_id == kimlik, (
        f"Kalıcı kayıttaki kimlik ({kayit.last_istek_id}) kullanıcının gördüğünden ({kimlik}) farklı"
    )


def test_tekrar_eden_hatada_SON_kimlik_saklanir(patlayan_client, db):
    """Kayıt parmak izine göre birleşir; saklanan son istektir (last_user_id konvansiyonu)."""
    patlayan_client.get(_PATLAYAN_UC)
    r2 = patlayan_client.get(_PATLAYAN_UC)
    kayitlar = db.query(ErrorLog).all()
    assert len(kayitlar) == 1, "Aynı hata için ikinci satır açıldı"
    assert kayitlar[0].occurrence_count == 2
    assert kayitlar[0].last_istek_id == r2.headers[BASLIK]


def test_log_satiri_kimligi_tasir():
    """Zincirin KALICI ucu log'dur: DB birleştirir, log her olayı ayrı tutar."""
    jeton = istek_id_var.set("logtest1")
    try:
        kayit = logging.LogRecord("t", logging.INFO, __file__, 1, "mesaj", None, None)
        IstekIdFiltresi().filter(kayit)
        satir = json.loads(JsonFormatter().format(kayit))
    finally:
        istek_id_var.reset(jeton)
    assert satir["istek_id"] == "logtest1"


def test_baglamsiz_log_satiri_da_alan_tasir():
    """Açılış/cron satırları kimliksizdir ama alan HER kayıtta olmalı — yoksa formatter patlar."""
    kayit = logging.LogRecord("t", logging.INFO, __file__, 1, "acilis", None, None)
    IstekIdFiltresi().filter(kayit)
    assert json.loads(JsonFormatter().format(kayit))["istek_id"] == "-"


def test_metin_formatinda_da_kimlik_var():
    """Development formatı da kimliği gösterir (yerelde hata ayıklamanın yarısı bu)."""
    from app.logging_config import _TEXT_FMT
    assert "%(istek_id)s" in _TEXT_FMT
    kayit = logging.LogRecord("t", logging.INFO, __file__, 1, "mesaj", None, None)
    IstekIdFiltresi().filter(kayit)
    assert "acbde234" in logging.Formatter(_TEXT_FMT).format(
        _kimlikli_kayit("acbde234")
    )


def _kimlikli_kayit(kimlik: str) -> logging.LogRecord:
    kayit = logging.LogRecord("t", logging.INFO, __file__, 1, "mesaj", None, None)
    kayit.istek_id = kimlik
    return kayit


# ══════════════════════════════════════════════════════════════════════
# 3. Kapsam kilidi (L11/H25): kimlik zincirinin halkaları sayılır
# ══════════════════════════════════════════════════════════════════════

def test_middleware_en_distadir():
    """Erken dönen yollar (gövde sınırı, kapasite reddi) da kimlik taşımalı.

    Starlette'te SON eklenen middleware EN DIŞTA çalışır. Korelasyon en son eklenmezse,
    tam da en çok teşhis gereken istekler (reddedilenler) kimliksiz kalır.
    """
    from app.main import _KorelasyonMiddleware
    adlar = [m.cls.__name__ for m in app.user_middleware]
    assert adlar[0] == _KorelasyonMiddleware.__name__, (
        f"Korelasyon middleware'i en dışta değil (sıra: {adlar})"
    )


def test_kapasite_reddi_de_kimlik_tasir(client, monkeypatch):
    """503 sırt basıncı yolunda da kimlik olmalı — kullanıcı en çok burada soru sorar."""
    monkeypatch.setattr("app.capacity.havuz_doygun_mu", lambda: True)
    r = client.get("/api/ready")
    assert r.status_code == 503
    assert len(r.headers.get(BASLIK, "")) >= 1
