"""
BUG #313 KAPISI — model adı SAĞLAYICIYA aittir, zincire değil.

ÖLÇÜLEN DEFEKT (1 Eyl 2026):
    `.env`: LLM_PROVIDER=fallback, LLM_MODEL=gemini-2.5-flash-lite
    `_build_anthropic()` aynı `LLM_MODEL`'i okuyordu → `LLM_PROVIDER=anthropic` diyen
    operatör Anthropic'e **gemini-2.5-flash-lite** gönderiyordu. Canlı kanıt:
    `anthropic.BadRequestError` alınmadan önce model adı zaten yanlıştı; ölçüm
    `_build_anthropic().model_name == "gemini-2.5-flash-lite"` ile doğrulandı.

    Sözleşme tutarsızdı: Groq/Together/DeepInfra/Ollama kendi `<ÖNEK>_MODEL`'ini okurken
    Gemini ve Anthropic TEK bir `LLM_MODEL`'i paylaşıyordu; Cerebras ve OpenRouter'ın ise
    model seçimi hiç yoktu.

NEDEN KAPI (yeşil test değil):
    Bu bir "yanlış değer" hatası değil, bir SÖZLEŞME hatasıdır — sessizdir. Yanlış model
    adı yalnız o sağlayıcı GERÇEKTEN çağrıldığında patlar; fallback zincirinde sıranın
    sonundaki halka aylarca denenmezse defekt görünmez kalır (koçun sağlayıcı zincirinin
    3/4'ünün ölü olduğu K0 baseline'ında tam olarak bu oldu).

MUTASYONLA KANITLANDI — kapının gerçekten tuttuğu, şu üç mutasyonun her birinin bu
dosyayı KIRMIZI yapmasıyla doğrulanır:
    M1: `saglayici_modeli` içinden `<ÖNEK>_MODEL` dalını kaldır  → test_ozel_degisken_kazanir düşer
    M2: `LLM_PROVIDER` eşitlik kontrolünü kaldır (LLM_MODEL herkese uygulansın)
                                                  → test_fallback_modunda_llm_model_sizmaz düşer
    M3: `LLM_MODEL` dalını tamamen kaldır         → test_adlandirilmis_saglayici_llm_model_onurlandirir düşer
"""
from __future__ import annotations

import pytest

from app.coach import (
    AnthropicProvider,
    CerebrasProvider,
    GeminiProvider,
    OpenRouterProvider,
    _build_anthropic,
    _build_cerebras,
    _build_gemini,
    _build_openrouter,
    saglayici_modeli,
)

# Yapıcılar ağ ÇAĞIRMAZ (yalnız istemci nesnesi kurar) → sahte anahtar yeterli.
_SAHTE = "test-anahtari-ag-cagrilmaz"

_ANAHTARLAR = {
    "GEMINI_API_KEY": _SAHTE,
    "ANTHROPIC_API_KEY": _SAHTE,
    "CEREBRAS_API_KEY": _SAHTE,
    "OPENROUTER_API_KEY": _SAHTE,
}

# Testi kirletebilecek TÜM model değişkenleri — her testte temizlenir.
_MODEL_DEGISKENLERI = (
    "LLM_MODEL", "GEMINI_MODEL", "ANTHROPIC_MODEL", "GROQ_MODEL",
    "CEREBRAS_MODEL", "OPENROUTER_MODEL", "TOGETHER_MODEL", "DEEPINFRA_MODEL",
)


@pytest.fixture
def ortam(monkeypatch):
    """Temiz ortam: anahtarlar var, model değişkenlerinin HİÇBİRİ yok."""
    for k, v in _ANAHTARLAR.items():
        monkeypatch.setenv(k, v)
    for k in _MODEL_DEGISKENLERI:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    return monkeypatch


def _model(p) -> str:
    """Sağlayıcılar modeli `model` ya da `model_name` alanında tutar."""
    for alan in ("model", "model_name"):
        if hasattr(p, alan):
            return getattr(p, alan)
    raise AssertionError(f"{type(p).__name__} model alanı taşımıyor")


# ============================================================
# 1. ASIL DEFEKT — fallback modunda LLM_MODEL sızmamalı
# ============================================================

def test_fallback_modunda_llm_model_sizmaz(ortam):
    """
    BUG #313'ün ta kendisi. `.env`'in GERÇEK hâli kurulur; Anthropic'in Gemini model
    adını ALMAMASI beklenir. Düzeltme öncesi bu test KIRMIZI'ydı.
    """
    ortam.setenv("LLM_PROVIDER", "fallback")
    ortam.setenv("LLM_MODEL", "gemini-2.5-flash-lite")

    assert _model(_build_anthropic()) == AnthropicProvider.DEFAULT_MODEL, (
        "Anthropic, zincir modundaki genel LLM_MODEL'i ALMAMALI — model adı sağlayıcıya aittir"
    )
    # Ters yön: Gemini de ayrıcalıklı değil; zincirde herkes kendi varsayılanını kullanır.
    assert _model(_build_gemini()) == GeminiProvider.DEFAULT_MODEL


def test_fallback_modunda_hicbir_saglayici_llm_model_almaz(ortam):
    """Sızıntı Anthropic'e özel değil — sözleşme zincirin TAMAMI için geçerli."""
    ortam.setenv("LLM_PROVIDER", "fallback")
    ortam.setenv("LLM_MODEL", "uydurma-model-adi")

    for kur, sinif in (
        (_build_anthropic, AnthropicProvider),
        (_build_gemini, GeminiProvider),
        (_build_cerebras, CerebrasProvider),
        (_build_openrouter, OpenRouterProvider),
    ):
        assert _model(kur()) == sinif.DEFAULT_MODEL, f"{sinif.NAME} genel LLM_MODEL'i aldı"


# ============================================================
# 2. ADLANDIRILMIŞ SAĞLAYICI — LLM_MODEL burada MEŞRUDUR
# ============================================================

def test_adlandirilmis_saglayici_llm_model_onurlandirir(ortam):
    """`LLM_PROVIDER=anthropic` diyen operatörün LLM_MODEL'i geçerlidir (belirsizlik yok)."""
    ortam.setenv("LLM_PROVIDER", "anthropic")
    ortam.setenv("LLM_MODEL", "claude-opus-5")

    assert _model(_build_anthropic()) == "claude-opus-5"
    # Aynı anda Gemini kurulursa O etkilenmez — LLM_PROVIDER onu adlandırmıyor.
    assert _model(_build_gemini()) == GeminiProvider.DEFAULT_MODEL


def test_adlandirma_buyuk_kucuk_harf_duyarsiz(ortam):
    ortam.setenv("LLM_PROVIDER", "  AnThRoPiC  ")
    ortam.setenv("LLM_MODEL", "claude-opus-5")
    assert _model(_build_anthropic()) == "claude-opus-5"


# ============================================================
# 3. SAĞLAYICIYA ÖZEL DEĞİŞKEN — her modda kazanır
# ============================================================

def test_ozel_degisken_kazanir(ortam):
    """`<ÖNEK>_MODEL` en yüksek önceliktir; zincir modunda da geçerlidir."""
    ortam.setenv("LLM_PROVIDER", "fallback")
    ortam.setenv("LLM_MODEL", "gemini-2.5-flash-lite")
    ortam.setenv("ANTHROPIC_MODEL", "claude-opus-5")

    assert _model(_build_anthropic()) == "claude-opus-5"
    assert _model(_build_gemini()) == GeminiProvider.DEFAULT_MODEL


def test_ozel_degisken_llm_model_i_gecer(ortam):
    """Adlandırılmış modda bile özel değişken önde gelir (öncelik 1 > 2)."""
    ortam.setenv("LLM_PROVIDER", "anthropic")
    ortam.setenv("LLM_MODEL", "claude-sonnet-5")
    ortam.setenv("ANTHROPIC_MODEL", "claude-opus-5")
    assert _model(_build_anthropic()) == "claude-opus-5"


# ============================================================
# 4. YENİ YETENEK — Cerebras ve OpenRouter artık sabitlenebilir
# ============================================================

def test_cerebras_ve_openrouter_pinlenebilir(ortam):
    """
    Düzeltme öncesi bu iki halka DAİMA DEFAULT_MODEL kullanıyordu; operatörün model
    seçme yolu yoktu (sağlayıcı bir modeli deprecate ederse kod değişikliği gerekiyordu —
    Cerebras'ta bir kez yaşandı, bkz. CerebrasProvider yorumu).
    """
    ortam.setenv("CEREBRAS_MODEL", "ozel-cerebras-modeli")
    ortam.setenv("OPENROUTER_MODEL", "ozel/openrouter-modeli")

    assert _model(_build_cerebras()) == "ozel-cerebras-modeli"
    assert _model(_build_openrouter()) == "ozel/openrouter-modeli"


# ============================================================
# 5. SAF SÖZLEŞME — yardımcının kendisi
# ============================================================

def test_yardimci_hicbir_degisken_yokken_none_doner(ortam):
    """None = 'sağlayıcı kendi DEFAULT_MODEL'ini kullansın'. Boş dize DEĞİL (L45 ruhu)."""
    assert saglayici_modeli("ANTHROPIC") is None


def test_yardimci_bos_dizeyi_yok_sayar(ortam):
    """`ANTHROPIC_MODEL=` (boş) bir seçim değildir — varsayılana düşmeli."""
    ortam.setenv("ANTHROPIC_MODEL", "   ")
    ortam.setenv("LLM_PROVIDER", "fallback")
    assert saglayici_modeli("ANTHROPIC") is None


# ============================================================
# 6. BUG #314 — zincirdeki her sağlayıcı TEK BAŞINA seçilebilir
# ============================================================

def test_zincirdeki_her_saglayici_tek_basina_secilebilir(ortam):
    """
    ÖLÇÜLEN DEFEKT: `build_provider` yalnız dört ad tanıyordu; zincir YEDİ sağlayıcı
    kuruyordu. Cerebras/OpenRouter/Together/DeepInfra hiç tek başına koşulamıyor, yani
    ölçülemiyordu. Zarar K1'de somutlaştı: zincirin üç halkası ölüyken "Cerebras ayakta mı?"
    sorusu SORULAMADI (`LLM_PROVIDER=cerebras` → "Bilinmeyen LLM_PROVIDER").
    Bir sağlayıcıyı zincire eklemek, onu ölçülebilir de yapmalıdır.
    """
    import app.coach as coach

    for ad in coach._ZINCIR_SIRASI:
        assert ad in coach._SAGLAYICI_KURUCULARI, f"zincirde olan '{ad}' seçilebilir değil"


def test_gecerli_adlar_hata_mesajinda_TURETILIR(ortam):
    """
    Elle yazılmış ad listesi sağlayıcı eklendiğinde sessizce eskir — nitekim eskimişti
    (dört sağlayıcı yıllarca zincirdeydi ama adı hiç listelenmedi).
    """
    import app.coach as coach

    ortam.setenv("LLM_PROVIDER", "yokboyle")
    with pytest.raises(ValueError) as e:
        coach.build_provider()
    mesaj = str(e.value)
    for ad in coach._SAGLAYICI_KURUCULARI:
        assert ad in mesaj, f"'{ad}' geçerli adlar listesinde görünmüyor"
    assert "fallback" in mesaj and "ollama" in mesaj


def test_kurucular_CAGRI_ANINDA_cozulur(ortam):
    """
    Sözlük fonksiyon REFERANSI tutarsa import anında donar ve bu depodaki yerleşik test
    dikişini (`monkeypatch.setattr(coach, "_build_gemini", ...)`) SESSİZCE etkisizleştirir —
    ilk sürümde tam olarak bu oldu ve `test_coverage_m88.py`'de iki test kırmızıya döndü.
    Zarar testle sınırlı değil: modül özniteliğini değiştiren biri davranışı değiştirdiğini
    sanır, oysa eski fonksiyon çağrılmaya devam eder.
    """
    import app.coach as coach

    ortam.setenv("LLM_PROVIDER", "gemini")

    # ISINMA ÇAĞRISI — MUTASYONUN BULDUĞU KÖR NOKTA:
    # Test ilk sürümünde doğrudan patch'leyip çağırıyordu. Bir ÖNBELLEKLİ uygulama
    # ("ilk çağrıda sözlüğü dondur") bu testi SIRA'ya bağlı olarak geçebiliyordu: patch
    # önce yapılırsa önbellek zaten patch'li hâli yakalıyor ve kapı susuyordu. Mutasyon
    # bunu gösterdi (kapı yeşil kaldı, defekti eski testler yakaladı). Isınma çağrısı,
    # patch'ten ÖNCE her türlü donmayı tetikler; böylece kapı sıradan bağımsız olur.
    coach.build_provider()

    nesne = object()
    ortam.setattr(coach, "_build_gemini", lambda: nesne)
    assert coach.build_provider() is nesne, "kurucu import anında donmuş — patch etkisiz"
