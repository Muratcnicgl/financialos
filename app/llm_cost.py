"""
LLM maliyet muhasebesi — TEK KAYNAK (BUG #274).

`api_call_log` tablosunun docstring'i ilk günden beri "gelecekte maliyet analizi icin de
veri kaynagi" diyor ve şemada `tokens_in` / `tokens_out` sütunları duruyor. Ölçüm, o vaadin
sistemde verilmiş olmadığını gösterdi (L33'ün maliyet karşılığı).

------------------------------------------------------------------------------
ÖLÇÜM (10 Ağu 2026 — 6 gerçekçi senaryo, gerçek uçlardan akıtılmış trafik)
------------------------------------------------------------------------------
13 GERÇEK sağlayıcı isteği → 13 defter satırı (sayım doğru, BUG #234'ün mirası). Ama:

| Eksen | Ölçülen |
|---|---|
| token'ı olan satır            | **0 / 13** |
| ÇALIŞAN modeli yazan satır    | 7 / 13     |
| isteği yiyen sağlayıcı        | 13 / 13    |

Yani harcanan **101.756 girdi + 7.944 çıktı token'ının tamamı** muhasebeye 0 olarak
düştü; "koç bu ay ne tuttu?" sorusunun defterde cevabı YOK.

Model ekseni iki ayrı biçimde kırıktı:
1. **Zincirde yanlış model.** Birincil kota dolup isteği YEDEK sağlayıcı karşıladığında
   satır `gemini-2.5-flash-lite (fallback: 1 ek provider)` yazıyordu — hem çalışan model
   yanlış (isteği llama-3.3-70b yedi) hem de sütunda **insan-okur bir etiket** vardı.
   Model başına maliyet, model bilinmeden hesaplanamaz.
2. **Amaç, model sütununu işgal etmişti.** Premortem ucu `model="premortem"`, aksiyon
   yansıması `model="reflection"` yazıyordu; yansıma ayrıca `provider="groq"`u SABİT
   yazıyor (isteği fiilen Gemini karşılasa bile). Amaç meşru bir sorudur — ama modelin
   sütununda değil, kendi sütununda cevaplanır (**L43**'ün buradaki karşılığı).

Token'ların sistemde tek göründüğü yer `reasoning_traces`'ti ve o da yalnız **%24'ünü**
yakalıyordu (koç sohbetinin ANA çağrısı; plan geçişi, retry denemesi, premortem ve
yansıma hiç); üstelik trace 90 günde siliniyor (`scheduler.py`) — yani muhasebe defteri
değil hata ayıklama yüzeyi.

------------------------------------------------------------------------------
SÖZLEŞME
------------------------------------------------------------------------------
1. **Token GERÇEK, para TÜREV — ama türev de dondurulur.** Satır hem token'ları hem
   yazma anındaki liste fiyatıyla hesaplanmış `est_cost_usd`'yi taşır. Fiyat listesi
   değişince geçmiş satırın parası değişmez; gerekirse token'lardan yeniden hesaplanır.
2. **Fiyat (SAĞLAYICI, MODEL) çiftinin özelliğidir.** Aynı model adı farklı sağlayıcıda
   farklı fiyatlıdır (`gpt-oss-120b` Groq'ta $0.15/$0.60; Cerebras'ta ayrı liste). Model
   adına bakan tek düzeyli tablo sekiz sağlayıcılı zincirde sessizce yanlış para üretir.
3. **Bilinmeyen fiyat 0 DEĞİLDİR.** Tabloda olmayan çift `None` döner ve operatör
   raporunda ayrı sayılır. Bilinen sıfır (yerel Ollama, `:free` varyantlar) bilinmeyenden
   ayrı tutulur — yeni bir model eklendiğinde maliyet "0" diye sessizce görünemez.
4. **Saklanan değer TAHMİNDİR.** Kod anahtarın hangi katmanda olduğunu bilemez (Gemini
   2.5 Flash-Lite'ın ücretsiz katmanı var). Değer liste fiyatına göre tahmindir; ücretsiz
   katmanda gerçek fatura 0'dır ve bağlayıcı kısıt zaten çağrı sayısıdır (kota muhasebesi).

Fiyat kaynakları ve karar gerekçesi: `docs/kalite-seruveni/research-log.md` (10 Ağu 2026).

GUNCELLEMELER
- 10 Agu 2026 BUG #274 fix: modul olusturuldu (LLM-006 + OBS-005). Fiyat tablosu
  (saglayici, model) ile anahtarlanir; bilinmeyen fiyat None doner, 0 DEGIL.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Tuple

# Para hassasiyeti: tek koç çağrısı ~0.001 USD mertebesinde → mikro-dolar çözünürlük.
KURUSLUK = Decimal("0.000001")
BIR_MILYON = Decimal("1000000")


@dataclass(frozen=True)
class Fiyat:
    """1 milyon token başına USD liste fiyatı + kaynağı (fiyatlar bayatlar, kaynak bayatlamaz)."""

    giris_usd_1m: Decimal
    cikis_usd_1m: Decimal
    kaynak: str
    tarih: str


def _f(giris: str, cikis: str, kaynak: str, tarih: str = "2026-08-10") -> Fiyat:
    return Fiyat(Decimal(giris), Decimal(cikis), kaynak, tarih)


# ============================================================
# YEREL SAĞLAYICILAR — bilinen SIFIR (yapısal, ada bakmadan)
# ============================================================
# Ollama kullanıcının kendi makinesinde koşar; sağlayıcı faturası YOKTUR. Bu, model
# adına değil sağlayıcının doğasına bağlı bir gerçektir — hangi model çalışırsa çalışsın
# maliyet 0'dır (elektrik bu defterin konusu değil).
YEREL_SAGLAYICILAR = frozenset({"ollama"})

SIFIR_FIYAT = Fiyat(Decimal("0"), Decimal("0"), "yerel calisma (saglayici faturasi yok)", "-")


# ============================================================
# FİYAT TABLOSU — (saglayici, model) → 1M token basina USD
# ============================================================
# Buraya yalnız DOĞRULANMIŞ fiyat girilir (KURAL R3). Doğrulanamayan sağlayıcı/model
# tabloda YER ALMAZ ve bilinmeyen olarak raporlanır — tahmin edilmiş bir fiyat,
# bilinmeyen bir fiyattan daha zararlıdır (kendinden emin yanlış sayı üretir).
FIYATLAR: Dict[Tuple[str, str], Fiyat] = {
    # --- Anthropic (kaynak: claude-api skill model/fiyat tablosu, cache 2026-06-24) ---
    ("anthropic", "claude-opus-5"): _f("5.00", "25.00", "anthropic model tablosu", "2026-06-24"),
    ("anthropic", "claude-opus-4-8"): _f("5.00", "25.00", "anthropic model tablosu", "2026-06-24"),
    ("anthropic", "claude-sonnet-5"): _f("3.00", "15.00", "anthropic model tablosu (standart; 31 Ağu 2026'ya kadar tanıtım 2.00/10.00)", "2026-06-24"),
    ("anthropic", "claude-haiku-4-5"): _f("1.00", "5.00", "anthropic model tablosu", "2026-06-24"),
    # --- Gemini (kaynak: ai.google.dev/gemini-api/docs/pricing — ücretli katman, metin) ---
    ("gemini", "gemini-2.5-flash-lite"): _f("0.10", "0.40", "ai.google.dev/gemini-api/docs/pricing"),
    ("gemini", "gemini-2.5-flash"): _f("0.30", "2.50", "ai.google.dev/gemini-api/docs/pricing"),
    # 2.5-pro fiyatı prompt uzunluğuna göre kademeli (>200k token'da 2.50/15.00).
    # Koç prompt'u ~8k olduğu için ≤200k kademesi yazıldı; uzun bağlama geçilirse GÜNCELLE.
    ("gemini", "gemini-2.5-pro"): _f("1.25", "10.00", "ai.google.dev/gemini-api/docs/pricing (<=200k prompt kademesi)"),
    # --- Groq (kaynak: console.groq.com/docs/models + model sayfaları) ---
    ("groq", "openai/gpt-oss-120b"): _f("0.15", "0.60", "console.groq.com/docs/model/openai/gpt-oss-120b"),
    ("groq", "llama-3.3-70b-versatile"): _f("0.59", "0.79", "console.groq.com/docs/models"),
    ("groq", "llama-3.1-8b-instant"): _f("0.05", "0.08", "console.groq.com/docs/models"),
    # --- Ücretsiz varyantlar: BİLİNEN sıfır (sağlayıcının kendi ücretsiz kademesi) ---
    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"): _f("0", "0", "openrouter ucretsiz varyant"),
    ("together", "meta-llama/llama-3.3-70b-instruct-turbo-free"): _f("0", "0", "together ucretsiz varyant"),
    # --- BİLİNMEYEN (kasten yok): cerebras/*, deepinfra/*, openrouter ücretli modeller.
    #     10 Ağu 2026'da fiyat sayfalarından teyit EDİLEMEDİ; tahmin yazılmadı.
}


def _anahtar(saglayici: Optional[str], model: Optional[str]) -> Tuple[str, str]:
    """Anahtar normalizasyonu: yalnız boşluk + büyük/küçük harf. Ad KIRPILMAZ.

    Sağlayıcı kimlikleri (`meta-llama/...`, `:free`) fiyatın parçasıdır; ön eki atmak
    farklı fiyatlı iki modeli aynı satıra düşürür.
    """
    return ((saglayici or "").strip().lower(), (model or "").strip().lower())


def fiyat_bul(saglayici: Optional[str], model: Optional[str]) -> Optional[Fiyat]:
    """(sağlayıcı, model) çiftinin liste fiyatı; bilinmiyorsa None (0 DEĞİL)."""
    ad, model_ad = _anahtar(saglayici, model)
    if ad in YEREL_SAGLAYICILAR:
        return SIFIR_FIYAT
    return FIYATLAR.get((ad, model_ad))


def fiyati_bilinmiyor(saglayici: Optional[str], model: Optional[str]) -> bool:
    """Operatör raporu için: bu çağrının parası hesaplanabiliyor mu?"""
    return fiyat_bul(saglayici, model) is None


def maliyet_usd(
    saglayici: Optional[str],
    model: Optional[str],
    tokens_in: Optional[int],
    tokens_out: Optional[int],
) -> Optional[Decimal]:
    """Tahmini USD maliyet; fiyat ya da token bilinmiyorsa None.

    None ile 0 arasındaki fark taşınır: 0 "bedava çalıştı" demektir (yerel/ücretsiz
    varyant), None "bilmiyoruz" demektir. Toplamda ikisini karıştırmak, bilinmeyen
    harcamayı sıfır harcama gibi gösterir.
    """
    fiyat = fiyat_bul(saglayici, model)
    if fiyat is None:
        return None
    if fiyat.giris_usd_1m == 0 and fiyat.cikis_usd_1m == 0:
        # Bilinen SIFIR: token bilinmese de sonuç kesin (0 × herhangi bir sayı = 0).
        # Yerel Ollama usage döndürmez; bu çağrıyı "fiyatı bilinmeyen" saymak yanlış olur.
        return Decimal("0").quantize(KURUSLUK)
    if tokens_in is None and tokens_out is None:
        return None  # sağlayıcı usage döndürmedi → token bilinmiyor, para uydurulmaz
    giris = Decimal(int(tokens_in or 0))
    cikis = Decimal(int(tokens_out or 0))
    toplam = (giris / BIR_MILYON) * fiyat.giris_usd_1m + (cikis / BIR_MILYON) * fiyat.cikis_usd_1m
    return toplam.quantize(KURUSLUK)
