# ADR-034 Revize — Koç Sağlayıcı Ücretsiz Alternatifler (Wave-3 M13)

**Tarih:** 13 Tem 2026 · **Durum:** ✅ REVİZE (ADR-028 "fiilen Gemini-only" güncellendi) · **Karar:** Ücretsiz kalınır (ücretli Wave-4). Fallback zinciri genişletildi.

## Bağlam
ADR-028: koç fiilen Gemini (Groq/Cerebras TPM eledi). Murat kararı: **ücretsiz kalınacak**, ücretli sağlayıcı Wave-4'e ertelendi. Görev: ücretsiz alternatiflerin kapsamlı D1 + entegrasyon + quality-per-cost.

**R3 (mevcut kod gerçeği):** `app/coach.py` ZATEN 6 provider içeriyor: Anthropic, Gemini, Groq, Cerebras, OpenRouter, Ollama — hepsi `LLMProvider` ABC + ortak OpenAI-uyumlu `_raw_chat` base (Groq/Cerebras/OpenRouter/Ollama). `build_provider()` fallback zinciri: `[groq → cerebras → gemini → openrouter → ollama]`, her biri key yoksa atlanır. Yani "5+ ücretsiz entegrasyon" büyük oranda tamam; bu revize onu **belgeler + genişletir**.

## D1 — Ücretsiz Sağlayıcı Karşılaştırması (13 Tem 2026)

| Sağlayıcı | Ücretsiz Limit | TR Erişim | Model Kalitesi (koç) | Tool-aware | Key | Durum |
|-----------|----------------|-----------|----------------------|------------|-----|-------|
| **Google Gemini** | 2.5 Flash ~günlük kotalı | ✅ | Yüksek (Türkçe iyi) | ✅ | GEMINI_API_KEY | **Birincil (fiilen)** — entegre |
| **Groq** | 8000 TPM (Llama 3.3 70B) | ✅ | Yüksek ama TPM<Türkçe-prompt → 413 | ✅ | GROQ_API_KEY | Entegre (TPM sınırı — reference memory) |
| **Cerebras** | gpt-oss-120b, hızlı | ✅ | Yüksek | ✅ | CEREBRAS_API_KEY | Entegre |
| **OpenRouter** | ~50/gün ücretsiz modeller, TPM-sınırsız | ✅ | Model-bağımlı (iyi) | ✅ | OPENROUTER_API_KEY | Entegre |
| **Ollama (yerel)** | Sınırsız (offline, egemen) | ✅ (yerel) | Orta (qwen2.5:7b) | ✅ | — (yerel) | Entegre — SON halka |
| **Together AI** | ~$1 kredi + free modeller | ✅ | Yüksek (Llama/Qwen) | ✅ (OpenAI-uyumlu) | TOGETHER_API_KEY | **Yeni eklendi** |
| **DeepInfra** | Free tier | ✅ | Yüksek | ✅ (OpenAI-uyumlu) | DEEPINFRA_API_KEY | **Yeni eklendi** |
| **Cloudflare Workers AI** | Free tier (Llama 3.3) | ✅ | Orta-yüksek | kısmi | CF_* | Wave-4 (ayrı auth şeması) |
| **HuggingFace Inference** | Free tier (rate-limitli) | ✅ | Model-bağımlı | değişken | HF_TOKEN | Wave-4 (tool-aware tutarsız) |
| **Mistral La Plateforme** | Free tier | ✅ | Yüksek | ✅ | MISTRAL_API_KEY | Wave-4 (opsiyonel) |
| **Anthropic** | 2026'da kalıcı free tier YOK (kredi bazlı) | ✅ | En yüksek | ✅ | ANTHROPIC_API_KEY | Entegre (ücretli — Wave-4 birincil adayı) |

## Quality-per-Cost Matrisi (koç kullanımı, ücretsiz odak)

- **En iyi kalite/ücretsiz:** Gemini 2.5 Flash (Türkçe + tool + kota makul) → **birincil**.
- **En yüksek throughput/ücretsiz:** OpenRouter (TPM-sınırsız, 50/gün yeterli) → **ikincil**.
- **Hız:** Cerebras/Groq (ama Groq TPM 8000 < Türkçe god-mode prompt → 413 riski, reference memory).
- **Egemenlik/offline:** Ollama (veri makineden çıkmaz, KVKK-mükemmel) → **son halka**.
- **Yeni ücretsiz throughput:** Together/DeepInfra (OpenAI-uyumlu, Llama/Qwen free) → ara halka.

## Karar (Fallback Zinciri Revizyonu)

**Yeni sıra:** `Gemini → OpenRouter → Cerebras → Together → DeepInfra → Groq → Ollama`

Gerekçe: (1) Gemini birincil (kalite+Türkçe); (2) OpenRouter TPM-sınırsız güvenilir yedek; (3) Cerebras hız; (4-5) Together/DeepInfra ücretsiz throughput; (6) Groq (TPM sınırı → sona); (7) Ollama egemen son-çare (offline). Her biri key yoksa atlanır (mevcut `_build_*` deseni). Circuit-breaker (günlük-kota eleme) korunur.

**Ücretli Wave-4:** Anthropic Claude (en yüksek kalite) birincil aday — Murat kota/bütçe kararınca.

## Uygulama (M13)
`TogetherProvider` + `DeepInfraProvider` (OpenAI-uyumlu, CerebrasProvider deseni) + `_build_together`/`_build_deepinfra` + `build_provider` zincir sırası revize. .env.example + API_KEY_TALEP. Test: mock + (key varsa) smoke.

**R3 sınırı:** yeni sağlayıcılar API key gerektirir (API_KEY_TALEP) → canlı smoke Murat'ta. Kod OpenAI-uyumlu kanıtlanmış deseni izler (Cerebras/OpenRouter ile aynı base).

## Kaynak
ADR-028, ADR-002 (fallback), research-log OpenRouter D1, reference memory (Groq TPM), coach.py mevcut 6-provider mimarisi.
