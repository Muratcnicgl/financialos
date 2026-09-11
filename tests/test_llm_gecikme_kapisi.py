"""
OBS-007 + OBS-016 / BUG #404 KAPISI — İSTEK SÜRESİ KAYNAKTA ÖLÇÜLÜR, BİLİNMEYEN NULL'DUR,
SAĞLAYICI SAĞLIĞI TEK UÇTAN OKUNUR.

Ölçülen (11 Eyl 2026, canlı defter): 311 `api_call_log` satırının 279'unda `duration_ms=0`.
Süre yalnız uçta, uçtan uca ölçülüp REZERVASYON satırına yazılıyordu; zincirin 2., 3.
halkaları ve yansıma çağrılarının tamamı "0 ms" görünüyordu — "bilinmeyen sıfır değildir"
(L45). OBS-016 "veri var, analiz yok" diyordu; veri de yarı yalandı.

Kilitlenen: (1) kota sarmalı isteğin KENDİ süresini ölçer ve `Cagri.sure_ms`e yazar;
(2) uzlaştırma satıra o süreyi yazar; rezervasyon/ek satır süresi bilinmiyorsa NULL;
(3) `/api/ops/llm` sağlayıcı başına sayım + p50/p95/p99, NULL süreler yüzdeliğe girmez.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import coach, llm_quota as kota
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import ApiCallLog, ApiCallStatus, Base, User
from app.routers import ops


@pytest.fixture
def gecici_saglayici():
    """Sarmalı sınayan geçici LLMProvider alt sınıfı; test bitince `__subclasses__`'tan düşer.

    Modül seviyesinde tanımlansaydı KVKK veri-işleyen envanteri kapısı onu "kodda aktif ama
    tabloda yok" diye yakalardı (BUG #372 sınıfı: test sınıfı gerçek kayıt defterine sızar).
    """
    import gc

    def uret(ad, gecikme=0.02, patla=False):
        class _Gecici(coach.LLMProvider):
            NAME = ad

            def __init__(self):
                self.model = "m"

            def _raw_chat(self, system_prompt, messages, tools):
                import time
                time.sleep(gecikme)
                if patla:
                    raise RuntimeError("boom")
                return coach.LLMResponse(text="ok", tool_calls=[], usage=None,
                                         provider_used=ad.lower(), model_name="m")

            def chat(self, system_prompt, messages, tools):
                return self._raw_chat(system_prompt, messages, tools)
        return _Gecici
    yield uret
    gc.collect()   # zayıf referanslı alt sınıf kaydı temizlensin


def test_kota_sarmali_istegin_kendi_suresini_olcer(gecici_saglayici):
    Sinif = gecici_saglayici("YavasTest")
    with kota.cagri_olcumu() as olcum:
        Sinif().chat("s", [], [])
    assert len(olcum) == 1
    assert olcum[0].sure_ms is not None and olcum[0].sure_ms >= 15, olcum[0]
    del Sinif


def test_coken_istek_de_sureyle_kaydedilir(gecici_saglayici):
    Sinif = gecici_saglayici("PatlarTest", gecikme=0, patla=True)
    with kota.cagri_olcumu() as olcum:
        with pytest.raises(RuntimeError):
            Sinif().chat("s", [], [])
    assert olcum[0].sure_ms is not None and olcum[0].sure_ms >= 0
    del Sinif


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)()
    ses.add(User(id=1, name="u")); ses.commit()
    yield ses
    ses.close()


def test_uzlastirma_her_satira_kendi_suresini_yazar_bilinmeyen_null(s):
    rez = kota.rezerve_et(s, 1, provider="gemini", model="?")
    assert rez.duration_ms is None, "rezervasyon süresi bilinmiyor — 0 yazılmamalı"
    olcum = [kota.Cagri("gemini", "g", sure_ms=120), kota.Cagri("openrouter", "o", sure_ms=340),
             kota.Cagri("groq", "q", sure_ms=None)]
    kota.ek_cagrilari_uzlastir(s, 1, olcum, rez)
    satirlar = s.query(ApiCallLog).order_by(ApiCallLog.id).all()
    assert [r.duration_ms for r in satirlar] == [120, 340, None]


def test_tamamla_sure_verilmezse_null_birakir(s):
    rez = kota.rezerve_et(s, 1, provider="gemini", model="?")
    kota.tamamla(s, rez, success=True)
    assert s.get(ApiCallLog, rez.id).duration_ms is None
    kota.tamamla(s, rez, success=True, duration_ms=77)
    assert s.get(ApiCallLog, rez.id).duration_ms == 77


def test_yuzdelik_en_yakin_sira():
    assert ops.yuzdelik([], 50) is None
    assert ops.yuzdelik([10], 99) == 10
    assert ops.yuzdelik([10, 20, 30, 40], 50) == 20
    assert ops.yuzdelik(list(range(1, 101)), 95) == 95
    assert ops.yuzdelik(list(range(1, 101)), 99) == 99


def test_ops_llm_ucu_saglayici_basina_sayar_null_sureyi_disarida_tutar(s):
    simdi = datetime.utcnow()
    def ekle(p, st, sure, gun=0):
        s.add(ApiCallLog(user_id=1, provider=p, model="m", status=st, duration_ms=sure,
                         called_at=simdi - timedelta(days=gun)))
    ekle("gemini", ApiCallStatus.success, 100); ekle("gemini", ApiCallStatus.success, 300)
    ekle("gemini", ApiCallStatus.failed, None); ekle("gemini", ApiCallStatus.rate_limited, None)
    ekle("groq", ApiCallStatus.success, None)
    ekle("gemini", ApiCallStatus.success, 5000, gun=30)   # pencere dışı
    s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        body = TestClient(app).get("/api/ops/llm?gun=7").json()
    finally:
        app.dependency_overrides.clear()
    assert body["gun"] == 7
    g = next(x for x in body["saglayicilar"] if x["provider"] == "gemini")
    assert (g["cagri"], g["basarili"], g["basarisiz"], g["hiz_sinirli"]) == (4, 2, 1, 1)
    assert g["basari_orani"] == 0.5 and g["olculen_sure"] == 2
    assert (g["p50_ms"], g["p95_ms"]) == (100, 300)
    q = next(x for x in body["saglayicilar"] if x["provider"] == "groq")
    assert q["olculen_sure"] == 0 and q["p50_ms"] is None and q["basari_orani"] == 1.0
