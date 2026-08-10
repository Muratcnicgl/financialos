"""
BUG #274 (LLM-006 + OBS-005) — LLM MALİYET DEFTERİ PARA SÜTUNLARINI HİÇ YAZMIYORDU.

`api_call_log` ilk günden beri "maliyet analizi icin de veri kaynagi" diye tanımlıydı ve
şemada `tokens_in`/`tokens_out` sütunları duruyordu. Ölçüm (6 gerçekçi senaryo, gerçek
uçlardan akıtılmış trafik) o vaadin sistemde verilmiş olmadığını gösterdi:

    13 gerçek sağlayıcı isteği → 13 defter satırı
    token'ı olan satır          0/13
    ÇALIŞAN modeli yazan satır  7/13   (zincirde yanlış model + amaç etiketi model sütununda)
    isteği yiyen sağlayıcı     13/13

Bu kapı üç şeyi kilitler:
1. **Satır, İSTEĞİN kimliğidir.** Her gerçek sağlayıcı isteği için bir satır; o satır isteği
   fiilen yiyen sağlayıcıyı, çalışan modeli, sağlayıcının döndürdüğü token'ları ve o anki
   liste fiyatıyla hesaplanmış tahmini maliyeti taşır.
2. **Amaç kendi sütununda.** `model` sütunu 'premortem'/'reflection' gibi amaç etiketi ya da
   'X (fallback: 1 ek provider)' gibi insan-okur etiket TAŞIMAZ.
3. **Bilinmeyen 0 değildir.** Fiyatı bilinmeyen (sağlayıcı, model) çifti None döner ve
   operatör raporunda ayrı sayılır; bilinen sıfır (yerel Ollama) bundan ayrıdır.
"""
from __future__ import annotations

import ast
import re
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import llm_cost, llm_quota
from app.coach import CoachEngine, FallbackProvider, LLMProvider, LLMResponse, _call_with_retry
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import ActionStatus, ApiCallLog, Base, PendingAction, User
from app.routers import coach as coach_router

KOK = Path(__file__).resolve().parent.parent


# ============================================================
# SAHTE SAĞLAYICILAR — gerçek desen (chat → _call_with_retry → _raw_chat)
# ============================================================

class _Sahte(LLMProvider):
    """NAME SINIF düzeyindedir: kota kancası `type(self).NAME` okur (gerçek sağlayıcılar gibi)."""

    NAME = "Gemini"

    def __init__(self, model="gemini-2.5-flash-lite", usage=True, kota_hatasi=False,
                 gecici_hata=0, metin="Durumun dengede görünüyor."):
        self.model = model
        self._usage = usage
        self._kota = kota_hatasi
        self._gecici = gecici_hata
        self.metin = metin
        self.token_in, self.token_out = 8213, 587
        self.istek = 0

    def _raw_chat(self, system_prompt, messages, tools):
        self.istek += 1
        if self._kota:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
        if self._gecici > 0:
            self._gecici -= 1
            raise RuntimeError("503 Service Unavailable")
        usage = ({"input_tokens": self.token_in, "output_tokens": self.token_out}
                 if self._usage else None)
        return LLMResponse(text=self.metin, tool_calls=[], usage=usage,
                           provider_used=self.NAME.lower(), model_name=self.model)

    def chat(self, system_prompt, messages, tools):
        return _call_with_retry(self._raw_chat, system_prompt, messages, tools)


def _uret(ad: str, **kw) -> _Sahte:
    return type(f"Sahte{ad}", (_Sahte,), {"NAME": ad})(**kw)


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
    u = User(name="olcum", email="olcum@x.com")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def client(db, kullanici, monkeypatch):
    monkeypatch.setenv("COACH_DAILY_USER_LIMIT", "500")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: kullanici
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _defter(db, uid):
    return db.query(ApiCallLog).filter(ApiCallLog.user_id == uid).order_by(ApiCallLog.id).all()


# ============================================================
# 1. SÖZLEŞME — satır isteğin kimliğini taşır
# ============================================================

def test_her_satir_kendi_isteginin_tokenini_ve_maliyetini_tasir(client, db, kullanici, monkeypatch):
    """Ölçülen defekt: 13 satırın 13'ünde de token NULL'dı → koçun maliyeti hesaplanamıyordu."""
    p = _uret("Gemini")
    monkeypatch.setattr(coach_router, "_engine", CoachEngine(provider=p))

    r = client.post("/api/coach/chat", json={"message": "Bu ay nasıl gidiyorum?"})
    assert r.status_code == 200, r.text
    assert p.istek >= 2, "Test kurulumu zayıf: iki-geçiş mimarisi ölçülemiyor"

    satirlar = _defter(db, kullanici.id)
    assert len(satirlar) == p.istek, (
        f"{p.istek} gerçek istek yapıldı ama deftere {len(satirlar)} satır düştü"
    )
    for s in satirlar:
        assert s.tokens_in == 8213 and s.tokens_out == 587, (
            f"Satır token taşımıyor (in={s.tokens_in}, out={s.tokens_out}) — sağlayıcı usage "
            "döndürdüğü hâlde muhasebeye düşmedi; maliyet hesaplanamaz"
        )
        assert s.est_cost_usd is not None, "Token biliniyor ama maliyet yazılmamış"


def test_maliyet_liste_fiyatiyla_dogru_hesaplanir(client, db, kullanici, monkeypatch):
    """8213 × $0.10/1M + 587 × $0.40/1M = $0.0010561 → 6 haneye yuvarlanır."""
    p = _uret("Gemini")
    monkeypatch.setattr(coach_router, "_engine", CoachEngine(provider=p))
    client.post("/api/coach/chat", json={"message": "Durum?"})

    beklenen = Decimal("0.001056")
    for s in _defter(db, kullanici.id):
        assert Decimal(s.est_cost_usd) == beklenen, (
            f"Maliyet {s.est_cost_usd}, beklenen {beklenen} — fiyat aritmetiği kaymış"
        )


def test_zincirde_satir_isteği_yiyen_saglayici_ve_calisan_modeli_yazar(
        client, db, kullanici, monkeypatch):
    """Ölçülen defekt: yedek cevapladığında satır BİRİNCİL modeli yazıyordu.

    Model başına maliyet, hangi modelin koştuğu bilinmeden hesaplanamaz.
    """
    birincil = _uret("Gemini", kota_hatasi=True)
    yedek = _uret("Groq", model="llama-3.3-70b-versatile")
    monkeypatch.setattr(coach_router, "_engine",
                        CoachEngine(provider=FallbackProvider([birincil, yedek])))

    r = client.post("/api/coach/chat", json={"message": "Bu ay nasıl gidiyorum?"})
    assert r.status_code == 200, r.text

    satirlar = _defter(db, kullanici.id)
    groq_satirlari = [s for s in satirlar if s.provider == "groq"]
    assert groq_satirlari, "İsteği yedek karşıladı ama deftere hiç groq satırı düşmedi"
    for s in groq_satirlari:
        assert s.model == "llama-3.3-70b-versatile", (
            f"Groq isteği '{s.model}' modeliyle kaydedildi — çalışan model değil"
        )
        # llama-3.3-70b: 8213×0.59/1M + 587×0.79/1M
        assert Decimal(s.est_cost_usd) == Decimal("0.005309")
    for s in satirlar:
        assert "fallback" not in (s.model or "").lower(), (
            f"model sütununda insan-okur etiket var: {s.model!r}"
        )


def test_coken_deneme_de_satir_yazar_ama_token_uydurulmaz(client, db, kullanici, monkeypatch):
    """Geçici hatada retry: istek ağa çıktı (satır var) ama token bilinmiyor (None, 0 DEĞİL)."""
    p = _uret("Gemini", gecici_hata=1)
    monkeypatch.setattr(coach_router, "_engine", CoachEngine(provider=p))
    client.post("/api/coach/chat", json={"message": "Durum?"})

    satirlar = _defter(db, kullanici.id)
    assert len(satirlar) == p.istek, "Çöken deneme muhasebeye düşmedi (kotayı yedi ama görünmüyor)"
    tokensiz = [s for s in satirlar if s.tokens_in is None]
    assert len(tokensiz) == 1, "Çöken denemenin token'ı uydurulmuş olmalı değil"
    assert tokensiz[0].est_cost_usd is None, (
        "Token bilinmiyorken maliyet yazılmış — bilinmeyen harcama sıfır harcama gibi görünür"
    )


# ============================================================
# 2. AMAÇ KENDİ SÜTUNUNDA (L43'ün maliyet karşılığı)
# ============================================================

def test_premortem_satiri_amaci_amac_sutununda_modeli_model_sutununda_tasir(
        client, db, kullanici, monkeypatch):
    """Ölçülen defekt: premortem satırı `model='premortem'` yazıyordu — model kayboluyordu."""
    import app.premortem as pm

    p = _uret("Groq", model="llama-3.3-70b-versatile")
    p.token_in, p.token_out = 3200, 900
    senaryo = ('{"id":"S%d","title":"Nakit sikismasi senaryosu %d",'
               '"probability_label":"orta","impact_tl":-1200.0,'
               '"narrative":"Karar basarisiz oldu. Sebebi su idi: nakit tamponu ay ortasinda '
               'tukendi ve kart borcu buyudu.",'
               '"mitigation":"Tampon tutari 2000 TL altina dusmeden harcamayi ertele."}')
    p.metin = '{"scenarios":[%s]}' % ",".join(senaryo % (i, i) for i in (1, 2, 3))
    monkeypatch.setattr(pm, "build_provider", lambda: p)

    pa = PendingAction(user_id=kullanici.id, action_type="add_transaction",
                       summary="test 320 TL", payload='{"amount": 320.0}',
                       status=ActionStatus.pending)
    db.add(pa)
    db.commit()

    r = client.post(f"/api/premortem/{pa.id}")
    assert r.status_code == 200, r.text

    satirlar = _defter(db, kullanici.id)
    assert len(satirlar) == 1
    s = satirlar[0]
    assert s.amac == "premortem", f"amaç sütunu {s.amac!r} — amaç kaydedilmiyor"
    assert s.model == "llama-3.3-70b-versatile", (
        f"model sütununda {s.model!r} var — amaç etiketi modeli eziyor"
    )
    assert s.provider == "groq", f"sağlayıcı {s.provider!r} — isteği fiilen yiyen değil"
    assert s.tokens_in == 3200 and s.est_cost_usd is not None


def test_amac_etiketi_hicbir_yolda_model_sutununa_yazilmaz(client, db, kullanici, monkeypatch):
    """Drift kilidi (davranışsal): defterdeki hiçbir model değeri amaç etiketi olmamalı."""
    p = _uret("Gemini")
    monkeypatch.setattr(coach_router, "_engine", CoachEngine(provider=p))
    client.post("/api/coach/chat", json={"message": "Durum?"})

    yasak = {"premortem", "reflection", "yansima", "koc", "coach"}
    for s in _defter(db, kullanici.id):
        assert (s.model or "").lower() not in yasak, f"model sütununda amaç etiketi: {s.model!r}"
        assert s.amac, "amaç sütunu boş — çağrının hangi yoldan geldiği kaybolmuş"


def test_kaynakta_amac_etiketi_model_argumani_olarak_gecmez():
    """Drift kilidi (statik): `model=` argümanına amaç etiketi yazan yeni yol eklenemez.

    Kaynaktan türetilir (AST): satır metnine değil çağrının ARGÜMANINA bakar, böylece
    yorum satırındaki 'model="premortem"' örneği sahte kırmızı üretmez.
    """
    yasak = {"premortem", "reflection", "yansima", "koc", "coach"}
    ihlal = []
    for dosya in sorted((KOK / "app").rglob("*.py")):
        agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
        for dugum in ast.walk(agac):
            if not isinstance(dugum, ast.Call):
                continue
            for kw in dugum.keywords:
                if kw.arg != "model" or not isinstance(kw.value, ast.Constant):
                    continue
                if str(kw.value.value).lower() in yasak:
                    ihlal.append(f"{dosya.relative_to(KOK)}:{dugum.lineno} model={kw.value.value!r}")
    assert not ihlal, (
        "Amaç etiketi `model=` argümanına yazılıyor — çalışan modeli ezer (BUG #274):\n  "
        + "\n  ".join(ihlal)
    )


def test_deftere_yazan_tek_yol_llm_quota():
    """Drift kilidi: `ApiCallLog(...)` yapıcısı yalnız muhasebe modülünde çağrılabilir.

    Ölçüm sırasında dördüncü bir yazar bulundu (`routers/coach._log_api_call`): ölüydü ama
    token/maliyet/amaç sözleşmesini bilmiyordu. Yeni bir yazar eklenirse burada kırılır.
    """
    izinli = {"app/llm_quota.py"}
    ihlal = []
    for dosya in sorted((KOK / "app").rglob("*.py")):
        rel = dosya.relative_to(KOK).as_posix()
        if rel in izinli:
            continue
        agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name) \
                    and dugum.func.id == "ApiCallLog":
                ihlal.append(f"{rel}:{dugum.lineno}")
    assert not ihlal, (
        "Defterin ikinci bir yazarı var — token/maliyet/amaç sözleşmesini atlar:\n  "
        + "\n  ".join(ihlal)
    )


# ============================================================
# 3. BİLİNMEYEN 0 DEĞİLDİR
# ============================================================

def test_bilinmeyen_fiyat_none_doner_sifir_degil():
    """Yeni bir model eklendiğinde maliyet sessizce 'bedava' görünemez."""
    assert llm_cost.fiyat_bul("cerebras", "gpt-oss-120b") is None
    assert llm_cost.maliyet_usd("cerebras", "gpt-oss-120b", 1000, 100) is None, (
        "Bilinmeyen fiyat 0 döndü — bilinmeyen harcama sıfır harcama gibi toplanır"
    )
    assert llm_cost.fiyati_bilinmiyor("cerebras", "gpt-oss-120b") is True


def test_yerel_saglayici_bilinen_sifirdir_token_bilinmese_bile():
    """Ollama kullanıcının makinesinde koşar: sağlayıcı faturası yok, usage de dönmez.

    Bunu 'fiyatı bilinmeyen' saymak operatörü yanıltır — fiyat BİLİNİYOR (sıfır).
    """
    assert llm_cost.fiyati_bilinmiyor("ollama", "qwen2.5:7b-instruct") is False
    assert llm_cost.maliyet_usd("ollama", "qwen2.5:7b-instruct", None, None) == Decimal("0.000000")


def test_ayni_model_adi_farkli_saglayicida_farkli_fiyatlidir():
    """Fiyat (sağlayıcı, model) çiftinin özelliğidir — tek düzeyli tablo yanlış para üretir."""
    groq = llm_cost.fiyat_bul("groq", "openai/gpt-oss-120b")
    assert groq is not None and groq.giris_usd_1m == Decimal("0.15")
    # Aynı model ailesi Cerebras'ta ayrı listede; teyit edilmediği için tabloda YOK.
    assert llm_cost.fiyat_bul("cerebras", "gpt-oss-120b") is None


def test_saglayici_usage_dondurmezse_maliyet_uydurulmaz(client, db, kullanici, monkeypatch):
    """Ücretli sağlayıcı token döndürmezse para hesaplanamaz — 0 yazmak yanlış olur."""
    p = _uret("Gemini", usage=False)
    monkeypatch.setattr(coach_router, "_engine", CoachEngine(provider=p))
    client.post("/api/coach/chat", json={"message": "Durum?"})

    for s in _defter(db, kullanici.id):
        assert s.tokens_in is None and s.est_cost_usd is None, (
            "Sağlayıcı usage döndürmediği hâlde maliyet yazılmış"
        )


# ============================================================
# 4. FİYAT TABLOSU SAĞLIĞI
# ============================================================

def test_fiyat_tablosu_tutarli():
    assert llm_cost.FIYATLAR, "Fiyat tablosu boş — hiçbir çağrının maliyeti hesaplanamaz"
    for (saglayici, model), fiyat in llm_cost.FIYATLAR.items():
        etiket = f"{saglayici}/{model}"
        assert saglayici == saglayici.lower() and model == model.lower(), (
            f"{etiket}: anahtar küçük harf değil — arama sessizce ıskalar"
        )
        assert fiyat.giris_usd_1m >= 0 and fiyat.cikis_usd_1m >= 0, f"{etiket}: negatif fiyat"
        assert fiyat.kaynak.strip(), f"{etiket}: kaynak yok — fiyat bayatladığında izlenemez"
        assert fiyat.tarih.strip(), f"{etiket}: tarih yok"


def test_canli_yapilandirmadaki_modellerin_fiyati_bilinir():
    """Canlı yol (Gemini koç + Groq yansıma) fiyatsız kalırsa maliyet raporu boş çıkar."""
    for saglayici, model in (
        ("gemini", "gemini-2.5-flash-lite"),
        ("groq", "llama-3.1-8b-instant"),
        ("groq", "llama-3.3-70b-versatile"),
    ):
        assert llm_cost.fiyat_bul(saglayici, model) is not None, (
            f"{saglayici}/{model} canlı yapılandırmada ama fiyat tablosunda yok"
        )


def test_model_adi_kirpilmaz():
    """`meta-llama/...:free` gibi ön ek/son ek fiyatın parçasıdır; kırpmak iki modeli birleştirir."""
    ucretsiz = llm_cost.fiyat_bul("openrouter", "meta-llama/llama-3.3-70b-instruct:free")
    assert ucretsiz is not None and ucretsiz.giris_usd_1m == 0
    assert llm_cost.fiyat_bul("openrouter", "meta-llama/llama-3.3-70b-instruct") is None, (
        "Ücretsiz varyantın fiyatı ücretli modele de uygulanıyor"
    )


# ============================================================
# 5. OPERATÖR YÜZEYİ — sessiz sıfır yok
# ============================================================

def test_operator_raporu_bilinmeyeni_ayri_sayar(db, kullanici):
    """`fiyatı bilinmeyen` ile `token döndürmeyen` ayrı raporlanır: sebepleri ve çözümleri ayrı."""
    from datetime import datetime, timedelta

    from scripts.beta_metrics import _maliyet

    db.add_all([
        # fiyatı bilinen, token'ı bilinen → toplama girer
        ApiCallLog(user_id=kullanici.id, provider="gemini", model="gemini-2.5-flash-lite",
                   tokens_in=8213, tokens_out=587, est_cost_usd=Decimal("0.001056"),
                   amac="koc", tool_calls_count=0, duration_ms=1),
        # token var ama fiyat tablosunda yok → fiyatı bilinmeyen
        ApiCallLog(user_id=kullanici.id, provider="cerebras", model="gpt-oss-120b",
                   tokens_in=100, tokens_out=10, est_cost_usd=None,
                   amac="koc", tool_calls_count=0, duration_ms=1),
        # sağlayıcı usage döndürmedi → token'ı bilinmeyen
        ApiCallLog(user_id=kullanici.id, provider="gemini", model="gemini-2.5-flash-lite",
                   tokens_in=None, tokens_out=None, est_cost_usd=None,
                   amac="premortem", tool_calls_count=0, duration_ms=1),
    ])
    db.commit()

    m = _maliyet(db, datetime.utcnow() - timedelta(days=1))
    assert m["fiyati_bilinmeyen_cagri"] == 1, "Fiyatı bilinmeyen çağrı görünmüyor"
    assert m["tokeni_bilinmeyen_cagri"] == 1, "Token döndürmeyen çağrı görünmüyor"
    assert m["tahmini_usd"] == pytest.approx(0.001056), (
        "Toplam yanlış — bilinmeyenler sıfır sayılıp toplama karışmış olabilir"
    )
    assert m["amac_bazinda_usd"] == {"koc": pytest.approx(0.001056)}


def test_maliyet_raporu_tahmin_oldugunu_soyler():
    """Ücretsiz katmanda gerçek fatura 0'dır; rapor bunu iddia etmemeli (dürüst etiket)."""
    kaynak = (KOK / "scripts" / "beta_metrics.py").read_text(encoding="utf-8")
    assert re.search(r"TAHMİN|tahmin", kaynak), (
        "Maliyet çıktısı kesin fatura gibi sunuluyor — liste fiyatı tahminidir"
    )
