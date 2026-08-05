"""
H17 / BUG #212 — EŞZAMANLI koç kullanımı: iki gerçek defekt.

**A) Kota yarışı (tavan delinebiliyordu).** Akış "sayacı OKU → LLM'i çağır (saniyeler) →
sayacı YAZ" idi. Sayaç ancak çağrı bitince arttığı için aynı anda gelen N istek aynı eski
sayıyı okuyup hepsi geçiyordu: hakkı 1 kalmış bir kullanıcı 20 paralel istek atarak 20 LLM
çağrısı yaptırabiliyordu. Bu, BUG #188'in var oluş sebebini (maliyet tavanı + paylaşılan
kotayı tek kişinin tüketememesi) fiilen iptal eder; açık betada doğrudan fatura riskidir.

**B) Muhasebe etiketi paylaşılan durumdan okunuyordu.** `engine.provider_name`,
FallbackProvider'ın **paylaşılan** `last_used_provider` alanını okur. İlk başarılı
çağrıdan sonra etiket "fallback(gemini)" olur; bu ad `PROVIDER_DAILY_LIMITS` içinde
YOKTUR → `limit=0` → **sağlayıcı günlük kota koruması sessizce ölür** (block hiç true
olmaz). Üstelik alan paylaşıldığı için etiket eşzamanlı BAŞKA kullanıcının çağrısına göre
değişir — aynı istek bazen "fallback", bazen "fallback(gemini)" muhasebeleşir.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, ApiCallLog, ApiCallStatus
import app.routers.coach as coach_router


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-coach-esz-0123456789abcdef")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "3")


@pytest.fixture
def oturum_fabrikasi(tmp_path):
    """Eşzamanlılık testi DOSYA tabanlı DB ister.

    Süitin geri kalanı in-memory + StaticPool kullanır; orada TEK bağlantı tüm
    session'larca paylaşılır. Bu dosyada üç istek gerçekten paralel koştuğu için o
    kurulum testin kendisini yarış hâline sokar (SQLAlchemy Session thread-safe
    DEĞİLDİR) — ölçmek istediğimiz üretim yarışını gizler. Burada her isteğe kendi
    bağlantısı verilir; kilitlenme SQLite'ın kendi yazma kilidiyle çözülür.
    """
    url = f"sqlite:///{tmp_path / 'eszamanlilik.db'}"
    eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(eng)
    fabrika = sessionmaker(bind=eng)
    kurulum = fabrika()
    kurulum.add(User(name="a"))
    kurulum.commit()
    kurulum.close()
    yield fabrika
    eng.dispose()


@pytest.fixture
def db(oturum_fabrikasi):
    """Testin kendi (istekten bağımsız) oturumu — kurulum + doğrulama için."""
    s = oturum_fabrikasi()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _yavas_motor(monkeypatch):
    """LLM çağrısını taklit eder ve YAVAŞLATIR — yarış penceresi gerçekçi genişlikte.

    Bariyer 3 taraflıdır ama bekleme SINIRLIDIR: kota kapısını geçen istek sayısı 3'ten
    azsa (429 alanlar motora hiç ulaşmaz) bariyer kısa sürede kırılır ve test asılmaz.
    Üçü de geçtiğinde ise üçü aynı anda LLM'in içinde olur — rezervasyon yoksa tavan delinir.
    """
    bariyer = threading.Barrier(3)

    class YavasMotor:
        provider_name = "FakeProvider"
        model = "fake-model"

        def chat(self, *a, **k):
            try:
                bariyer.wait(timeout=1.5)
            except threading.BrokenBarrierError:
                pass
            return {"reply": "ok", "proposed_actions": [], "cockpit_snapshot": None,
                    "coach_memory_id": None}

    monkeypatch.setattr(coach_router, "_get_engine", lambda: YavasMotor())
    return bariyer


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


def _paralel_istek(client, adet: int) -> list[int]:
    kodlar: list[int] = []
    kilit = threading.Lock()

    def _git():
        r = client.post("/api/coach/chat", json={"message": "merhaba"})
        with kilit:
            kodlar.append(r.status_code)

    isler = [threading.Thread(target=_git) for _ in range(adet)]
    for t in isler:
        t.start()
    for t in isler:
        t.join(timeout=20)
    return kodlar


def test_eszamanli_istekler_tavani_delemez(client, db):
    """Hakkı 1 kalmışken 3 paralel istek: yalnız 1'i geçmeli."""
    u = db.query(User).first()
    now = datetime.utcnow()
    for _ in range(2):   # tavan 3 → 1 hak kaldı
        db.add(ApiCallLog(user_id=u.id, provider="gemini", model="t", called_at=now,
                          status=ApiCallStatus.success, duration_ms=1, tool_calls_count=0))
    db.commit()

    kodlar = _paralel_istek(client, 3)
    gecen = sum(1 for k in kodlar if k == 200)
    assert gecen == 1, f"Eşzamanlı istekler tavanı deldi: {kodlar}"
    assert sorted(kodlar) == [200, 429, 429]


def test_reddedilen_istek_sayaci_kirletmez(client, db):
    """429 alan isteğin rezervasyonu geri alınmalı — yoksa kullanıcı hakkını
    kullanmadan kaybeder (sonraki gün değil, aynı gün içinde ceza)."""
    u = db.query(User).first()
    now = datetime.utcnow()
    for _ in range(2):
        db.add(ApiCallLog(user_id=u.id, provider="gemini", model="t", called_at=now,
                          status=ApiCallStatus.success, duration_ms=1, tool_calls_count=0))
    db.commit()

    _paralel_istek(client, 3)
    toplam = db.query(ApiCallLog).filter(ApiCallLog.user_id == u.id).count()
    assert toplam == 3, f"Reddedilen istekler sayaca yazıldı (toplam={toplam}, tavan=3)"


def test_tavan_kapaliyken_rezervasyon_engellemez(client, db, monkeypatch):
    """COACH_DAILY_USER_LIMIT=0 → tavan kapalı; hiçbir istek reddedilmemeli."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "0")
    kodlar = _paralel_istek(client, 3)
    assert kodlar == [200, 200, 200], kodlar


# ── B) Muhasebe etiketi ──────────────────────────────────────────────────────

def test_fallback_etiketi_paylasilan_durumdan_okunmaz():
    """last_used_provider dolduğunda etiket 'fallback(gemini)' olup kota korumasını
    öldürüyordu; ayrıca eşzamanlı başka kullanıcının çağrısına göre değişiyordu."""
    from app.coach import FallbackProvider, LLMProvider
    from app.routers.coach import _muhasebe_saglayici_adi, _daily_constrained_provider
    from app.routers.coach import PROVIDER_DAILY_LIMITS

    class Sahte(LLMProvider):
        NAME = "Gemini"
        model = "m"

        def chat(self, *a, **k):
            raise NotImplementedError

    fb = FallbackProvider([Sahte()])
    fb.last_used_provider = "Gemini"          # başka bir isteğin bıraktığı iz

    class Motor:
        provider = fb

    etiket = _muhasebe_saglayici_adi(Motor())
    assert etiket == "fallback", f"Etiket paylaşılan duruma bağlı: {etiket}"
    hedef = _daily_constrained_provider(etiket)
    assert hedef in PROVIDER_DAILY_LIMITS, \
        "Muhasebe etiketi günlük-limit tablosuyla eşleşmiyor → kota koruması ölü"


def test_tek_saglayicida_etiket_kendi_adi():
    from app.coach import LLMProvider
    from app.routers.coach import _muhasebe_saglayici_adi

    class Sahte(LLMProvider):
        NAME = "Anthropic"
        model = "m"

        def chat(self, *a, **k):
            raise NotImplementedError

    class Motor:
        provider = Sahte()

    assert _muhasebe_saglayici_adi(Motor()) == "anthropic"
