"""
LLM-039 / BUG #439 KAPISI — KOÇ KALİTE ÖZETİ: İZDEKİ SİNYALLER TOPLANIR.

Ölçülen (13 Eyl 2026): `reasoning_traces` grounding ihlali/zayıf beraat (FINAL_ANSWER gözlemi,
BUG #325/#273), retry adımları (LLM_CALL 'Retry:' niyeti), hata ve gecikme sütunlarını zaten
taşıyor; ama "ne sıklıkta" sorusunun cevabı yoktu. `/api/ops/koc-kalite` göçsüz bir agregasyon.

Kilitlenen: sayımlar sinyalin GERÇEK yazıldığı yerden (FINAL_ANSWER inference/observation,
LLM_CALL intent/error/latency); eski izlerde alan yoksa 0; pencere dışı iz sayılmaz; `gun`
sınırlı; kimlik zorunlu.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Base, OperationName, ReasoningTrace, User
from app.routers.ops import _zayif_sayisi, koc_kalitesi


@pytest.fixture
def s():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    ses = sessionmaker(bind=eng)(); ses.add(User(id=1, name="u")); ses.commit()
    yield ses; ses.close()


def _iz(ses, op, *, intent=None, observation=None, inference=None, error=None, latency=None,
        gi=None, co=None, gun_once=0):
    ses.add(ReasoningTrace(user_id=1, trace_id="t", step_index=0, operation_name=op, intent=intent,
                           observation=observation, inference=inference, error=error, latency_ms=latency,
                           usage_input_tokens=gi, usage_output_tokens=co,
                           created_at=datetime.utcnow() - timedelta(days=gun_once)))  # tz-exempt: test verisi


def test_zayif_ayristirici():
    assert _zayif_sayisi("reply_len=10, grounding_ok=True, grounding_checked=2, grounding_zayif=3") == 3
    assert _zayif_sayisi("reply_len=10, grounding_ok=True") == 0
    assert _zayif_sayisi(None) == 0


def test_sayimlar_gercek_sinyalden(s):
    F, L = OperationName.FINAL_ANSWER, OperationName.LLM_CALL
    _iz(s, F, observation="grounding_ok=True, grounding_zayif=0")
    _iz(s, F, observation="grounding_ok=False, grounding_zayif=0", inference="grounding_violation: ['1.234 TL']")
    _iz(s, F, observation="grounding_ok=True, grounding_zayif=2")
    _iz(s, F, observation="reply_len=5")                       # eski iz: alan yok → 0
    _iz(s, L, intent="Ana yanit uretimi", latency=100, gi=10, co=5)
    _iz(s, L, intent="Retry: propose_action zorla", latency=300, gi=20, co=7)
    _iz(s, L, intent="Ana yanit uretimi", error="timeout", latency=900)
    _iz(s, F, observation="grounding_ok=False", inference="grounding_violation: x", gun_once=10)   # pencere dışı
    s.commit()
    k = koc_kalitesi(s, 7)
    assert (k.cevap, k.grounding_ihlal, k.grounding_zayif) == (4, 1, 1)
    assert (k.retry, k.llm_hata, k.llm_cagri) == (1, 1, 3)
    assert (k.p50_gecikme_ms, k.p95_gecikme_ms) == (300, 900)
    assert (k.girdi_token, k.cikti_token) == (30, 12)


def test_uc_kimlik_ister_ve_gun_sinirli(s):
    c = TestClient(app)
    # Test ortamında kimlik kapalı → kullanıcı yoksa 404 (canlıda 401); her iki durumda da 200 DEĞİL.
    assert c.get("/api/ops/koc-kalite").status_code in (401, 404)
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        r = c.get("/api/ops/koc-kalite?gun=500")
        assert r.status_code == 200 and r.json()["gun"] == 90
        assert r.json()["cevap"] == 0 and r.json()["p50_gecikme_ms"] is None
    finally:
        app.dependency_overrides.clear()
