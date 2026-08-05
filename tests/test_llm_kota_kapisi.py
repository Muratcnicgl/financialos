"""
D07 + D16 (BUG #228) — LLM KOTASI TEK UCA CIVATALANMIŞTI, DİĞER YOLLAR TAVANI SIFIRLIYORDU.

ADR-041 / BUG #188'in tüm amacı "bir kullanıcı paylaşılan API anahtarını/faturayı tek başına
tüketemesin" idi; dayatma yalnız `POST /api/coach/chat` içindeydi.

Denetimin çalıştırdığı kanıt (D07):
    COACH-1: 200  COACH-2: 429            ← tavan dayatılıyor, kota DOLU
    PREMORTEM kodları: [200, 200, 200, 200, 200]
    PREMORTEM LLM üretim çağrısı sayısı: 5
    ApiCallLog değişimi: 0                ← hiçbiri sayaca yazılmadı
Ve tek bir aksiyon için 6 kez üretim (BUG #137 cache'i cockpit hash'ine bağlı; kullanıcı
kotasız bir uçla bakiyeyi değiştirince hash değişiyor).

D16 aynı sınıf: `POST /api/actions/{id}/approve` arka planda kotasız + kayıtsız bir Groq
çağrısı yapıyordu (yansıma/insight yazıcısı).

Zarar: ücretsiz kademede paylaşılan anahtar tükenir → TÜM beta kullanıcılarının koçu
"cevap veremedi"ye düşer; ücretli kademede doğrudan fatura. Ayrıca `ApiCallLog`'a hiç
yazılmadığı için `scripts/beta_metrics.py` maliyet/hata metrikleri bu trafiği HİÇ görmez —
operatör patlamayı ölçtükten sonra bile nedenini bulamaz.

Kök düzeltme: kota muhasebesi uçtan SÖKÜLÜP paylaşılan `app/llm_quota` modülüne alındı ve
LLM üreten her kullanıcı-tetikli yol oradan geçiyor. Bu dosya hem davranışı hem de
"yeni bir LLM yolu eklenince kapı unutulmasın" değişmezini kilitler (L11).
"""
from __future__ import annotations

import ast
import re
from datetime import datetime
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
APP = KOK / "app"

# Kota kapısından geçmesi BEKLENMEYEN yollar — her biri gerekçeli.
# (Dosyada `# kota-exempt: <gerekçe>` satırı da bulunmalı; gerekçe koda yazılır.)
_MUAF = {
    "app/coach.py",           # motor: kota `routers/coach.py` içinde rezerve edilir
    "app/premortem.py",       # motor: kota `routers/premortem.py` içinde rezerve edilir
    "app/coach_insights.py",  # cron (sistem-tetikli): kullanıcı döngüye sokamaz
}


def _llm_cagiran_dosyalar() -> list[str]:
    """`provider.chat(...)` yapan veya `build_provider()` çağıran app/ dosyaları."""
    bulunan = []
    for yol in sorted(APP.rglob("*.py")):
        metin = yol.read_text(encoding="utf-8")
        if re.search(r"\.chat\(\s*$|\.chat\(\s*\w|build_provider\(\)", metin, re.M):
            if re.search(r"provider\.chat\(|build_provider\(\)|GroqProvider\(", metin):
                bulunan.append(yol.relative_to(KOK).as_posix())
    return bulunan


# ============================================================
# 1. KAPSAM TABANI (L11 — kapı kaç yolu ölçüyor)
# ============================================================

def test_kapsam_tabani_llm_yollari_bulunuyor():
    """Tarama hiçbir şey bulmuyorsa alttaki kapı sessizce boş koşar."""
    yollar = _llm_cagiran_dosyalar()
    assert len(yollar) >= 4, (
        f"LLM çağıran dosya taraması yalnız {len(yollar)} sonuç verdi ({yollar}) — "
        "tarama bozulmuş olabilir, kapı kör kalır"
    )


def test_her_llm_yolu_ya_kotadan_gecer_ya_gerekceli_muaf():
    """Yeni bir LLM yolu eklenince kota kapısı sessizce atlanamaz."""
    eksikler = []
    for yol in _llm_cagiran_dosyalar():
        metin = (KOK / yol).read_text(encoding="utf-8")
        kotadan_geciyor = "llm_quota" in metin
        muaf_isareti = re.search(r"#\s*kota-exempt:\s*\S+", metin) is not None
        if kotadan_geciyor:
            continue
        if yol in _MUAF and muaf_isareti:
            continue
        eksikler.append(yol)
    assert not eksikler, (
        f"Bu yollar LLM üretiyor ama kota muhasebesinden geçmiyor (ve gerekçeli muaf da "
        f"değil): {eksikler}. ADR-041 tavanı bu yollardan sıfırlanır."
    )


def test_muaf_listesi_bayat_degil():
    """Muaf sayılan dosya artık LLM çağırmıyorsa liste temizlenmeli (ölü muafiyet birikmesin)."""
    llm_yollari = set(_llm_cagiran_dosyalar())
    bayat = sorted(_MUAF - llm_yollari)
    assert not bayat, f"Muaf listesinde LLM çağırmayan dosyalar var: {bayat}"


# ============================================================
# 2. DAVRANIŞ — premortem (D07)
# ============================================================

from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.main import app  # noqa: E402
from app.dependencies import get_db, get_current_user  # noqa: E402
from app.models import (  # noqa: E402
    Base, User, ApiCallLog, ApiCallStatus, ActionStatus, PendingAction,
)
from app.premortem import PremortemResult, PremortemScenario  # noqa: E402


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def kullanici(db):
    u = User(name="murat", email="m@x.com")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def aksiyon(db, kullanici):
    import json
    p = PendingAction(user_id=kullanici.id, action_type="add_transaction",
                      payload=json.dumps({"amount": 1500.0}), summary="Market",
                      status=ActionStatus.pending)
    db.add(p)
    db.commit()
    return p


@pytest.fixture
def client(db, kullanici):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: kullanici
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _sahte_sonuc(action_id: int) -> PremortemResult:
    return PremortemResult(
        action_id=action_id,
        scenarios=[
            PremortemScenario(
                id=f"S{i}", title=f"Test senaryosu {i}", probability_label="orta",
                impact_tl=-500.0,
                narrative="Bu aksiyon basarisiz oldu cunku test sebebi yeterince uzun yazildi.",
                mitigation="Test mitigation aksiyonu yazildi.",
            )
            for i in range(1, 4)
        ],
        provider_used="fake", model_name="fake-model",
    )


def _kota_doldur(db, user_id: int, adet: int):
    for _ in range(adet):
        db.add(ApiCallLog(user_id=user_id, provider="fake", model="m",
                          status=ApiCallStatus.success, tool_calls_count=0, duration_ms=1,
                          called_at=datetime.utcnow()))
    db.commit()


def test_premortem_kotayi_sayaca_yazar(client, db, kullanici, aksiyon, monkeypatch):
    """Her premortem üretimi ApiCallLog'a düşmeli — yoksa maliyet metrikleri kör."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "80")
    onceki = db.query(ApiCallLog).count()
    with patch("app.routers.premortem.generate_premortem",
               side_effect=lambda **kw: _sahte_sonuc(kw["action_id"])):
        r = client.post(f"/api/premortem/{aksiyon.id}")
    assert r.status_code == 200, r.text
    assert db.query(ApiCallLog).count() == onceki + 1, \
        "Premortem LLM üretimi sayaca hiç yazılmadı (denetim D07)"


def test_kota_doluyken_premortem_429(client, db, kullanici, aksiyon, monkeypatch):
    """Kotası dolmuş kullanıcı premortem ile sınırsız üretim yaptıramamalı."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "2")
    _kota_doldur(db, kullanici.id, 2)
    with patch("app.routers.premortem.generate_premortem",
               side_effect=AssertionError("kota doluyken LLM çağrılmamalı")):
        r = client.post(f"/api/premortem/{aksiyon.id}")
    assert r.status_code == 429, f"Kota dolu iken premortem {r.status_code} döndü"


def test_kota_kapaliysa_premortem_calisir(client, db, kullanici, aksiyon, monkeypatch):
    """COACH_DAILY_USER_LIMIT=0 → tavan kapalı (L6: kapı ürünü kilitlemez)."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "0")
    _kota_doldur(db, kullanici.id, 50)
    with patch("app.routers.premortem.generate_premortem",
               side_effect=lambda **kw: _sahte_sonuc(kw["action_id"])):
        r = client.post(f"/api/premortem/{aksiyon.id}")
    assert r.status_code == 200, r.text


def test_onbellekten_donen_premortem_kota_harcamaz(client, db, kullanici, aksiyon, monkeypatch):
    """LLM çağrılmadıysa (cache) sayaç artmamalı — kullanıcı haksız yere cezalanmaz."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "80")
    with patch("app.routers.premortem.generate_premortem",
               side_effect=lambda **kw: _sahte_sonuc(kw["action_id"])):
        assert client.post(f"/api/premortem/{aksiyon.id}").status_code == 200
    ilk_sayi = db.query(ApiCallLog).count()

    with patch("app.routers.premortem.generate_premortem",
               side_effect=AssertionError("cache varken LLM çağrılmamalı")):
        r = client.post(f"/api/premortem/{aksiyon.id}")
    assert r.status_code == 200, r.text
    assert r.json()["cached"] is True
    assert db.query(ApiCallLog).count() == ilk_sayi, \
        "Önbellekten dönen premortem kota harcadı"


# ============================================================
# 3. DAVRANIŞ — aksiyon onayı arka plan yansıması (D16)
# ============================================================

def _yansimayi_kos(db, monkeypatch, kullanici, llm_yan_etki):
    """`_run_reflection` arka plan görevini test DB'siyle koşar."""
    import app.database as db_mod
    import app.coach as coach_mod
    from app.routers import actions as actions_mod

    monkeypatch.setattr(db_mod, "SessionLocal", lambda: db)
    with patch.object(coach_mod, "GroqProvider", side_effect=llm_yan_etki) as sahte:
        actions_mod._run_reflection(
            user_id=kullanici.id, action_type="add_transaction",
            summary="Market harcaması",
            payload_str='{"amount": 1500.0, "category": "market"}',
        )
    return sahte


def test_aksiyon_yansimasi_kota_doluyken_llm_cagirmaz(db, kullanici, monkeypatch):
    """Arka plan yansıması kotasız bir kaçak yol olmamalı (D16)."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "1")
    monkeypatch.setenv("GROQ_API_KEY", "sahte-anahtar")
    _kota_doldur(db, kullanici.id, 1)

    sahte = _yansimayi_kos(db, monkeypatch, kullanici,
                           AssertionError("kota doluyken LLM çağrılmamalı"))
    assert sahte.call_count == 0, "Kota dolu iken arka plan yansıması LLM çağırdı"
    assert db.query(ApiCallLog).count() == 1, "Reddedilen rezervasyon sayaçta bırakıldı"


def test_aksiyon_yansimasi_sayaca_yazar(db, kullanici, monkeypatch):
    """Yansıma koşarsa muhasebeye düşmeli (maliyet metrikleri onu görsün)."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "80")
    monkeypatch.setenv("GROQ_API_KEY", "sahte-anahtar")

    class _BosCevap:
        tool_calls: list = []

    class _SahteProvider:
        def __init__(self, *a, **kw):
            pass

        def chat(self, **kw):
            return _BosCevap()

    onceki = db.query(ApiCallLog).count()
    import app.database as db_mod
    import app.coach as coach_mod
    from app.routers import actions as actions_mod
    monkeypatch.setattr(db_mod, "SessionLocal", lambda: db)
    monkeypatch.setattr(coach_mod, "GroqProvider", _SahteProvider)
    actions_mod._run_reflection(
        user_id=kullanici.id, action_type="add_transaction", summary="Market",
        payload_str='{"amount": 1500.0, "category": "market"}',
    )
    assert db.query(ApiCallLog).count() == onceki + 1, \
        "Aksiyon yansıması LLM çağrısı sayaca hiç yazılmadı (denetim D16)"
