"""
D14 + D15 (BUG #234) — LLM KOTA MUHASEBESİ GERÇEK KULLANIMI ÖLÇMÜYORDU.

İki ayrı defekt, tek kök: sayaç neyi saydığını yanlış biliyordu.

**D14 — "paylaşılan sağlayıcı kotası" fiilen KULLANICI-BAŞINA sayılıyordu.**
`_today_call_count` sorgusu `ApiCallLog.user_id == user_id` ile filtreliydi; oysa
`UsageInfo` sözleşmesi (coach.py:85) "Yukarıdakiler sağlayıcının PAYLAŞILAN günlük
kotasıdır" diyordu. Sonuç: 1500/gün Gemini tavanı hiç ölçülmüyordu — B kullanıcısı 2000
çağrı yapmışken A'nın gördüğü sayaç 0'dı. Kişisel tavan (80) her zaman önce dolduğu için
`warn` (%80) ve `block` (%100) dalları **matematiksel olarak erişilemezdi** (ölü koruma +
ölü UI: Coach.jsx'in block bandı hiç görünemezdi).

**D15 — tavan ÇAĞRI değil MESAJ sayıyordu.**
Bir `/api/coach/chat` isteği iki-geçiş mimarisi (STEP B.5 plan + STEP C ana çağrı) ve retry
dalları yüzünden 1-4 gerçek sağlayıcı isteği üretiyor, ama muhasebeye TEK satır yazılıyordu.
ADR-041'in ilan ettiği "80 çağrı ~ 40 mesaj/gün" sözleşmesi diskte YANLIŞTI: 80 satır = 80
mesaj ≈ 160+ gerçek istek. Paylaşılan sayaç da aynı oranda az gösterdiği için operatörün
uyarı eşiği 2 kat geç ateşlerdi.

Kök düzeltme: sayım noktası **gerçek sağlayıcı isteğine** taşındı. `LLMProvider` alt
sınıflarının `_raw_chat`'i `__init_subclass__` ile otomatik sarmalanır (yeni sağlayıcı
eklenince kanca UNUTULAMAZ — L14 fail-closed), ölçüm `app/llm_quota` içindeki bir
ContextVar'da toplanır ve istek sonunda rezervasyonla uzlaştırılır. Paylaşılan sayaç
artık kullanıcı filtresizdir.
"""
from __future__ import annotations

import inspect
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import llm_quota
from app.coach import CoachEngine, FallbackProvider, LLMProvider, LLMResponse, _call_with_retry
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import ApiCallLog, ApiCallStatus, Base, User
from app.routers import coach as coach_router


# ============================================================
# FIXTURE'LAR
# ============================================================

@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def kullanici_a(db):
    u = User(name="a", email="a@x.com")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def kullanici_b(db):
    u = User(name="b", email="b@x.com")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def client(db, kullanici_a):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: kullanici_a
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _cagri_yaz(db, user_id: int, adet: int, provider: str = "gemini"):
    for _ in range(adet):
        db.add(ApiCallLog(user_id=user_id, provider=provider, model="m",
                          status=ApiCallStatus.success, tool_calls_count=0, duration_ms=1,
                          called_at=datetime.utcnow()))
    db.commit()


class SayanProvider(LLMProvider):
    """Gerçek sağlayıcı deseninde (chat → _call_with_retry → _raw_chat) sahte sağlayıcı.

    NAME "Gemini": günlük tavanı ilan edilmiş tek sağlayıcı o (PROVIDER_DAILY_LIMITS) —
    muhasebe yolunun tamamı gerçek yapılandırmayla ölçülsün, patch'le kısa devre edilmesin.
    """

    NAME = "Gemini"
    model = "sahte-model"

    def __init__(self):
        self.sayi = 0

    def _raw_chat(self, system_prompt, messages, tools):
        self.sayi += 1
        return LLMResponse(text="Durumun dengede görünüyor.", tool_calls=[],
                           provider_used="gemini", model_name="sahte-model")

    def chat(self, system_prompt, messages, tools):
        return _call_with_retry(self._raw_chat, system_prompt, messages, tools)


@pytest.fixture
def sahte_motor(monkeypatch):
    """Router'ın paylaşılan motorunu TEK sağlayıcılı (alternatifsiz) motorla değiştirir."""
    saglayici = SayanProvider()
    monkeypatch.setattr(coach_router, "_engine", CoachEngine(provider=saglayici))
    return saglayici


@pytest.fixture
def zincir_motor(monkeypatch):
    """Yedekli (fallback) motor — birincil tükenirse zincir devam eder."""
    birincil, yedek = SayanProvider(), SayanProvider()
    monkeypatch.setattr(coach_router, "_engine",
                        CoachEngine(provider=FallbackProvider([birincil, yedek])))
    return birincil


# ============================================================
# 1. D14 — PAYLAŞILAN SAĞLAYICI SAYACI
# ============================================================

def test_paylasilan_sayac_diger_kullanicilarin_cagrilarini_da_sayar(db, kullanici_a, kullanici_b):
    """Sağlayıcı kotası paylaşılandır: B'nin tükettiği A'nın sayacında görünmeli (D14)."""
    _cagri_yaz(db, kullanici_b.id, 1200)
    usage = coach_router._build_usage_info(db, kullanici_a.id, "gemini")
    assert usage.today_count == 1200, (
        f"Paylaşılan sağlayıcı sayacı {usage.today_count} gösterdi — başka kullanıcıların "
        "tükettiği kota görünmüyor (D14: sayaç kullanıcı-başına filtreliydi)"
    )
    assert usage.warn is True, "Paylaşılan kotanın %80'i aşıldı ama warn ateşlemedi"


def test_paylasilan_sayac_dolunca_block_atesler(db, kullanici_a, kullanici_b):
    """%100 dalı erişilebilir olmalı — eskiden matematiksel olarak ölüydü (D14)."""
    _cagri_yaz(db, kullanici_b.id, coach_router.GEMINI_DAILY_LIMIT)
    usage = coach_router._build_usage_info(db, kullanici_a.id, "gemini")
    assert usage.block is True, "Paylaşılan günlük tavan dolu ama block dalı hâlâ ölü"


def test_kisisel_sayac_kullanici_basina_kalir(db, kullanici_a, kullanici_b):
    """Regresyon: kişisel tavan (ADR-041) paylaşılan sayaçtan bağımsız kalmalı."""
    _cagri_yaz(db, kullanici_b.id, 300)
    usage = coach_router._build_usage_info(db, kullanici_a.id, "gemini")
    assert usage.user_today_count == 0, (
        "Kişisel sayaç başka kullanıcının çağrılarını saydı — kişisel tavan A'yı "
        "B'nin kullanımı yüzünden kilitler"
    )


def test_tek_saglayici_modunda_paylasilan_tavan_dolunca_chat_429(
        client, db, kullanici_b, sahte_motor, monkeypatch):
    """Alternatifi olmayan sağlayıcıda tavan dolduysa istek reddedilir (D14)."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "80")
    _cagri_yaz(db, kullanici_b.id, coach_router.GEMINI_DAILY_LIMIT)

    r = client.post("/api/coach/chat", json={"message": "Durumum nasıl?"})
    assert r.status_code == 429, (
        f"Paylaşılan Gemini tavanı dolu iken chat {r.status_code} döndü — "
        "ücretsiz kademe sessizce aşılır"
    )
    assert sahte_motor.sayi == 0, "Tavan dolu iken sağlayıcıya yine de istek gitti"


def test_fallback_modunda_paylasilan_tavan_kilitlemez(
        client, db, kullanici_b, zincir_motor, monkeypatch):
    """L6: zincirde alternatif sağlayıcı varken ürün kilitlenmez — yalnız uyarılır."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "80")
    _cagri_yaz(db, kullanici_b.id, coach_router.GEMINI_DAILY_LIMIT)

    r = client.post("/api/coach/chat", json={"message": "Durumum nasıl?"})
    assert r.status_code == 200, (
        f"Fallback zincirinde alternatif sağlayıcı varken chat {r.status_code} döndü — "
        "çalışan ürün gereksiz kilitlendi"
    )
    assert r.json()["usage"]["warn"] is True, \
        "Fallback modda da operatör paylaşılan kotanın dolduğunu görmeli"


# ============================================================
# 2. D15 — TAVAN GERÇEK ÇAĞRIYI SAYAR
# ============================================================

def test_usage_ucu_zincirde_arayuzu_kilitlemez(client, db, kullanici_b, zincir_motor):
    """`block` = "istek reddedilecek": yedekli zincirde arayüz girişi kapatılmamalı."""
    _cagri_yaz(db, kullanici_b.id, coach_router.GEMINI_DAILY_LIMIT)
    r = client.get("/api/coach/usage")
    assert r.status_code == 200, r.text
    veri = r.json()
    assert veri["block"] is False, \
        "Yedek sağlayıcı varken arayüz kilitlendi (çalışan ürün kapatılır)"
    assert veri["warn"] is True, "Operatör paylaşılan kotanın dolduğunu göremiyor"


def test_usage_ucu_zincir_etiketinde_rozeti_oldurmez(client, db, kullanici_b, zincir_motor):
    """Etiket çalışma-anı durumundan türetilirse ('Fallback(Gemini)') limit kaybolur (BUG #212 sınıfı)."""
    zincir_motor_saglayici = coach_router._engine.provider
    zincir_motor_saglayici.last_used_provider = "Gemini"   # ilk başarılı çağrıdan sonraki hal
    _cagri_yaz(db, kullanici_b.id, 900)
    veri = client.get("/api/coach/usage").json()
    assert veri["daily_limit"] == coach_router.GEMINI_DAILY_LIMIT, \
        "Zincir etiketi yüzünden günlük limit bilinmiyor → kullanım rozeti sessizce ölü"
    assert veri["today_count"] == 900


def test_bir_chat_gercek_saglayici_cagrisi_kadar_satir_yazar(
        client, db, kullanici_a, sahte_motor, monkeypatch):
    """ADR-041'in birimi ÇAĞRI'dır: iki-geçiş mimarisi 2 satır yazmalı (D15)."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "80")
    r = client.post("/api/coach/chat", json={"message": "Bu ay nasıl gidiyorum?"})
    assert r.status_code == 200, r.text
    assert sahte_motor.sayi >= 2, (
        f"Test kurulumu zayıf: motor yalnız {sahte_motor.sayi} sağlayıcı çağrısı yaptı, "
        "iki-geçiş mimarisi ölçülemiyor"
    )
    satir = db.query(ApiCallLog).filter(ApiCallLog.user_id == kullanici_a.id).count()
    assert satir == sahte_motor.sayi, (
        f"{sahte_motor.sayi} gerçek sağlayıcı çağrısı yapıldı ama muhasebeye {satir} satır "
        "yazıldı — ilan edilen maliyet tavanı gerçeğin altında kalır (D15)"
    )


def test_kisisel_tavan_gercek_cagri_sayisiyla_dolar(
        client, db, kullanici_a, sahte_motor, monkeypatch):
    """Tavan 2 çağrı iken tek mesaj (2 çağrı) tavanı doldurur → ikinci mesaj 429 (D15)."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "2")
    ilk = client.post("/api/coach/chat", json={"message": "Bu ay nasıl gidiyorum?"})
    assert ilk.status_code == 200, ilk.text
    assert sahte_motor.sayi >= 2

    ikinci = client.post("/api/coach/chat", json={"message": "Peki geçen ay?"})
    assert ikinci.status_code == 429, (
        f"Tavan {2} çağrı iken 2 çağrı harcanmış olmasına rağmen ikinci mesaj "
        f"{ikinci.status_code} döndü — tavan gerçek maliyeti değil mesajı sayıyor"
    )


def test_usage_kisisel_sayaci_gercek_cagriyi_gosterir(
        client, db, kullanici_a, sahte_motor, monkeypatch):
    """Kullanıcıya gösterilen sayaç da gerçek çağrı sayısı olmalı (tutarlılık)."""
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "80")
    r = client.post("/api/coach/chat", json={"message": "Bu ay nasıl gidiyorum?"})
    assert r.status_code == 200, r.text
    assert r.json()["usage"]["user_today_count"] == sahte_motor.sayi


def test_cagri_olcumu_saglayici_bazinda_toplar(db, kullanici_a):
    """Ölçüm hangi sağlayıcının kaç istek yediğini ayırmalı (paylaşılan sayaç doğru dolsun)."""
    with llm_quota.cagri_olcumu() as olcum:
        llm_quota.cagri_kaydet("Gemini")
        llm_quota.cagri_kaydet("gemini")
        llm_quota.cagri_kaydet("Groq")
    assert olcum == {"gemini": 2, "groq": 1}


def test_olcum_kapsami_disinda_kayit_patlamaz():
    """Kanca ölçüm kapsamı olmayan yollarda (cron, script) sessizce no-op olmalı."""
    llm_quota.cagri_kaydet("gemini")   # exception yükseltmemeli


# ============================================================
# 3. SINIF TARAMASI (L11) — koç dışındaki LLM yolları da gerçek çağrıyı sayar
# ============================================================

def test_premortem_gercek_cagri_sayisi_kadar_satir_yazar(
        client, db, kullanici_a, monkeypatch):
    """Zincir/retry premortem'de de birden fazla gerçek istek üretir (D15 sınıfı)."""
    import json as _json

    from app.models import ActionStatus, PendingAction
    from app.premortem import PremortemResult, PremortemScenario
    from app.routers import premortem as premortem_router

    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "80")
    aksiyon = PendingAction(user_id=kullanici_a.id, action_type="add_transaction",
                            payload=_json.dumps({"amount": 1500.0}), summary="Market",
                            status=ActionStatus.pending)
    db.add(aksiyon)
    db.commit()

    saglayici = SayanProvider()

    def _iki_gercek_istek(**kw):
        """Zincirin ikinci halkaya düşmesini taklit eder (2 gerçek sağlayıcı isteği)."""
        for _ in range(2):
            saglayici.chat(system_prompt="s", messages=[], tools=[])
        return PremortemResult(
            action_id=kw["action_id"],
            scenarios=[
                PremortemScenario(id=f"S{i}", title=f"Test senaryosu {i}",
                                  probability_label="orta", impact_tl=-500.0,
                                  narrative="Bu aksiyon basarisiz oldu cunku sebep yeterince uzun.",
                                  mitigation="Test mitigation aksiyonu yazildi.")
                for i in range(1, 4)
            ],
            provider_used="gemini", model_name="sahte-model",
        )

    monkeypatch.setattr(premortem_router, "generate_premortem", _iki_gercek_istek)
    r = client.post(f"/api/premortem/{aksiyon.id}")
    assert r.status_code == 200, r.text
    assert saglayici.sayi == 2
    assert db.query(ApiCallLog).count() == 2, (
        "Premortem 2 gerçek sağlayıcı isteği yaptı ama sayaca 1 satır yazıldı — "
        "aynı sınıf defekt (D15) koç dışındaki yolda açık kalmış"
    )


def test_yansima_denenen_her_modeli_sayar(db, kullanici_a, monkeypatch):
    """Aksiyon yansıması iki modeli sırayla dener; ikisi de gerçek istektir (D15 sınıfı)."""
    import app.coach as coach_mod
    import app.database as db_mod
    from app.routers import actions as actions_mod

    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "80")
    monkeypatch.setenv("GROQ_API_KEY", "sahte-anahtar")

    class _IlkiCokenProvider(LLMProvider):
        NAME = "Groq"
        cagrilar: list = []

        def __init__(self, api_key=None, model=None):
            self.model = model

        def _raw_chat(self, system_prompt, messages, tools):
            _IlkiCokenProvider.cagrilar.append(self.model)
            if len(_IlkiCokenProvider.cagrilar) == 1:
                raise RuntimeError("ilk model dustu")
            return LLMResponse(text="", tool_calls=[], provider_used="groq",
                               model_name=self.model)

        def chat(self, system_prompt, messages, tools):
            return self._raw_chat(system_prompt, messages, tools)

    monkeypatch.setattr(db_mod, "SessionLocal", lambda: db)
    monkeypatch.setattr(coach_mod, "GroqProvider", _IlkiCokenProvider)
    actions_mod._run_reflection(
        user_id=kullanici_a.id, action_type="add_transaction", summary="Market",
        payload_str='{"amount": 1500.0, "category": "market"}',
    )
    assert len(_IlkiCokenProvider.cagrilar) == 2, "Test kurulumu: iki model denenmeliydi"
    assert db.query(ApiCallLog).count() == 2, (
        "Yansıma iki modeli de sağlayıcıya gönderdi ama sayaca 1 satır yazıldı (D15 sınıfı)"
    )


# ============================================================
# 4. STATİK KAPI — sayım kancası atlanamaz (L11/L14)
# ============================================================

def _somut_saglayicilar() -> list[type]:
    """FallbackProvider hariç tüm LLMProvider alt sınıfları (o zincir, kendi isteği yok)."""
    return [c for c in LLMProvider.__subclasses__()
            if c is not FallbackProvider and not inspect.isabstract(c)]


def test_kapsam_tabani_saglayici_sayisi():
    """Tarama boşalırsa alttaki kapı sessizce kör koşar (L11)."""
    saglayicilar = _somut_saglayicilar()
    assert len(saglayicilar) >= 6, (
        f"Yalnız {len(saglayicilar)} somut sağlayıcı bulundu ({saglayicilar}) — "
        "tarama bozulmuş olabilir"
    )


def test_her_saglayici_sayim_kancasindan_gecer():
    """Yeni bir sağlayıcı eklendiğinde kota sayımı sessizce atlanamaz (L14 fail-closed)."""
    kancasiz = [c.__name__ for c in _somut_saglayicilar()
                if not getattr(getattr(c, "_raw_chat", None), "_kota_sarmali", False)]
    assert not kancasiz, (
        f"Bu sağlayıcıların gerçek istekleri kota sayımına girmiyor: {kancasiz}. "
        "Muhasebe onların trafiğini göremez (maliyet metrikleri kör kalır)."
    )


def test_zincir_saglayicisi_cift_saymaz():
    """FallbackProvider alt sağlayıcıyı çağırır; kendisi de sayarsa maliyet 2 kat şişer."""
    assert not getattr(getattr(FallbackProvider, "_raw_chat", None), "_kota_sarmali", False)


def test_sarmalayici_imzayi_korur():
    """Sarmalama sağlayıcı sözleşmesini bozmamalı (keyword çağrılar kırılmasın)."""
    for c in _somut_saglayicilar():
        parametreler = list(inspect.signature(c._raw_chat).parameters)
        assert parametreler[:4] == ["self", "system_prompt", "messages", "tools"], (
            f"{c.__name__}._raw_chat imzası sarmalama sonrası bozuldu: {parametreler}"
        )
