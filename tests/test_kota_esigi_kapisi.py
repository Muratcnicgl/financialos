"""
OBS-025 / BUG #405 KAPISI — KULLANIM ROZETİ VE %80 UYARISI ÖLÇÜLEN KOTAYA BAĞLI.

Ölçülen (11 Eyl 2026): `PROVIDER_DAILY_LIMITS = {"gemini": 1500}`. Gemini ücretsiz kademe
10 Ağu'da canlı 429 gövdesiyle **20/gün** ölçülmüştü (app/coach.py başlığı bunu yazıyor);
router 1500'de kalmıştı → 20 çağrı %1,3, "%80 uyarısı" ve "%100 blok" erişilemezdi.
Üretim sağlayıcısı OpenRouter (50/gün) sözlükte hiç yoktu → rozet canlıda hep %0.
"Tavan var, uyarı yok" teşhisi de eksikti: uyarı VARDI, tavan YANLIŞTI.

Kilitlenen: limitler ölçülen varsayılanla env'den; OpenRouter dahil; 16/20 → warn; env ile
ezilebilir; koddaki Gemini ölçümü (20) ile router tutarlı.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import ApiCallLog, ApiCallStatus, Base, User
from app.routers import coach as coach_router

KOK = Path(__file__).resolve().parent.parent


def test_varsayilanlar_olculen_degerler_ve_openrouter_dahil():
    assert coach_router.PROVIDER_DAILY_LIMITS == {"gemini": 20, "openrouter": 50}


def test_koddaki_gemini_olcumu_router_ile_ayni():
    """app/coach.py başlığı '**N istek/gün**' der; router aynı N'i taşımalı — 1500 böyle çürüdü."""
    bas = (KOK / "app" / "coach.py").read_text(encoding="utf-8")[:2000]
    m = re.search(r"\*\*(\d+) istek/gün\*\*", bas)
    assert m, "coach.py başlığında ölçülen Gemini kotası yok"
    assert int(m.group(1)) == coach_router._gunluk_limit("GEMINI_DAILY_LIMIT", 20) == 20


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)(); s.add(User(id=1, name="u")); s.commit()
    yield s; s.close()


def _cagri(db, provider, n):
    for _ in range(n):
        db.add(ApiCallLog(user_id=1, provider=provider, model="m", status=ApiCallStatus.success))
    db.commit()


def test_openrouter_16_cagri_yuzde_80_uyari(db):
    _cagri(db, "openrouter", 16)
    u = coach_router._build_usage_info(db, 1, "openrouter")
    assert (u.daily_limit, u.percentage, u.warn) == (50, 32.0, False)
    _cagri(db, "openrouter", 24)   # 40/50
    u = coach_router._build_usage_info(db, 1, "openrouter")
    assert (u.percentage, u.warn, u.block) == (80.0, True, False)   # uyarı var, blok yok
    _cagri(db, "openrouter", 10)   # 50/50
    u = coach_router._build_usage_info(db, 1, "openrouter")
    assert (u.percentage, u.block) == (100.0, True)
    assert coach_router._build_usage_info(db, 1, "openrouter", alternatif_var=True).block is False


def test_env_ile_ezilir(monkeypatch):
    monkeypatch.setenv("GEMINI_DAILY_LIMIT", "1500")
    monkeypatch.setenv("OPENROUTER_DAILY_LIMIT", "0")
    m = importlib.reload(coach_router)
    try:
        assert m.PROVIDER_DAILY_LIMITS == {"gemini": 1500}   # 0 = "günlük limit bilinmiyor"
    finally:
        monkeypatch.delenv("GEMINI_DAILY_LIMIT"); monkeypatch.delenv("OPENROUTER_DAILY_LIMIT")
        importlib.reload(coach_router)
