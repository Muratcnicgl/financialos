"""
BE-025 — kullanım/limit takibi fallback modda doğru çalışmalı. Eskiden provider != 'gemini'
iken (fallback dahil) her zaman %0 / 999999 dönüyordu → günlük Gemini kotası izlenmiyor,
pre-call block koruması FALLBACK'te ölüydü. Fix: fallback → gemini kotası raporlanır, gerçek
alt-sağlayıcı loglanır.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, ApiCallLog, ApiCallStatus
from app.routers.coach import (
    _build_usage_info, _daily_constrained_provider, GEMINI_DAILY_LIMIT,
)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


def _log(db, provider, n=1):
    for _ in range(n):
        db.add(ApiCallLog(user_id=1, provider=provider, model="m",
                          status=ApiCallStatus.success, tool_calls_count=0, duration_ms=10))
    db.commit()


def test_daily_constrained_provider_fallback_gemini():
    assert _daily_constrained_provider("fallback") == "gemini"
    assert _daily_constrained_provider("gemini") == "gemini"
    assert _daily_constrained_provider("groq") == "groq"


def test_fallback_gemini_kotasini_raporlar(db):
    # fallback modda gerçek çağrılar gemini olarak loglanır (BE-025 fix)
    _log(db, "gemini", 3)
    u = _build_usage_info(db, 1, "fallback")
    assert u.daily_limit == GEMINI_DAILY_LIMIT       # 999999 DEĞİL
    assert u.today_count == 3
    assert u.percentage == round(3 / GEMINI_DAILY_LIMIT * 100, 1)
    assert u.percentage > 0.0                          # eskiden hep 0.0 idi


def test_gunluk_limit_block_fallbackte_calisir(db):
    _log(db, "gemini", GEMINI_DAILY_LIMIT)             # kota doldu
    u = _build_usage_info(db, 1, "fallback")
    assert u.block is True                              # pre-call koruma artık fallback'te de aktif
    assert u.warn is True


def test_tpm_saglayici_yaniltici_yuzde_vermez(db):
    # Groq günlük limiti YOK (TPM) → % 0 ama daily_limit 0 (yanıltıcı 999999 değil)
    _log(db, "groq", 5)
    u = _build_usage_info(db, 1, "groq")
    assert u.daily_limit == 0
    assert u.percentage == 0.0
    assert u.today_count == 5                           # sayı yine görünür
    assert u.block is False


def test_gemini_dogrudan_hala_calisir(db):
    _log(db, "gemini", 1500)
    u = _build_usage_info(db, 1, "gemini")
    assert u.percentage == 100.0 and u.block is True
