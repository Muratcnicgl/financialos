# Research Log (KURAL D1 — sektör araştırmaları)

Her mimari/teknoloji kararı öncesi 2-3 sektör referansı; bulgular burada.

## 2026-07-12 — OpenRouter (koç sağlayıcı fallback, ADR-028)
**Soru:** Gemini-only kısıtına (Groq/Cerebras TPM aşımı) alternatif fallback var mı?
**Bulgu:** OpenRouter = birleşik LLM router (300+ model, 60+ sağlayıcı, tek API key). Ücretsiz katman: 20+ model (Llama 3.3 70B, GPT-OSS 120B, Qwen3 Coder, Nemotron); ücretsiz lineup rotasyonlu. **Rate limit istek-bazlı: 50/gün (kredisiz) veya 1000/gün ($10+), 20/dk — TPM sınırı YOK** → zengin koç prompt'u (~8000 token) için Groq/Cerebras'tan daha uygun. `openrouter/free` auto-router (Şub 2026) uygun ücretsiz modele yönlendirir. Fallback-faturalama: yalnız başarılı çağrı ücretlendirilir. PAYG %5.5 platform ücreti; BYOK opsiyonu.
**Sonuç:** Wave-3 en güçlü koç-fallback adayı. Canlı kalite/latency/TR-erişim testi gerekli (ADR-034). Wave-2'de eklenmez (mevcut Gemini yeterli).
**Kaynaklar:** openrouter.ai/pricing · openrouter.ai/openrouter/free · openrouter.ai/blog/tutorials/free-llm-apis-compared
