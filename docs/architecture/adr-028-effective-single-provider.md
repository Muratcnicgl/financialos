# ADR-028 — Koç fiilen tek-sağlayıcı gerçeği (Gemini-only, Wave-2)

**Tarih:** 12 Temmuz 2026 · **Durum:** ⚠️ **SUPERSEDED by ADR-034 + ADR-034-revize (Wave-3 M13)** · **İlgili:** ADR-002, ADR-034, memory `reference_groq_tpm_limiti`

> **SUPERSEDED (17 Tem 2026, tam-proje-durum-raporu §B7):** Bu ADR Wave-2'nin "fiilen Gemini-only"
> gerçeğini kaydediyordu. Wave-3 M13'te koç 8 sağlayıcıya genişledi (Anthropic/Gemini/Groq/Cerebras/
> OpenRouter/Together/DeepInfra/Ollama) + `LLM_PROVIDER=fallback` 7-halkalı zincir. Artık geçerli olan
> ADR-034 + ADR-034-revize. Bu belge tarihsel kayıt olarak korunur.

## Bağlam
ADR-002 provider-agnostic bir `FallbackProvider` zinciri tanımlar (Groq → Cerebras → Gemini → OpenRouter → Ollama). Ancak **disk gerçeği (R3):** zengin veride koç isteği ~8000+ token; Groq HEM Cerebras (gpt-oss-120b, ücretsiz ~8000 TPM) TPM'i aşar → RESIL-008 circuit breaker ikisini de eler → **koç FİİLEN yalnız Gemini'de çalışır.** Bu bir kod defekti değil, dış kısıt; prompt-trim RİSKLİ (davranış sözleşmesini — KURAL SIFIR, rapor formatı — zayıflatır, docs uyarısı).

## Karar
**Wave-2 için Gemini-only fiilen kabul edilir.** ADR-002'nin provider-agnostic YAPISI korunur (fallback zinciri, sağlayıcı soyutlaması) — bu sağlayıcı çeşitliliğini gelecekte geri açar. Ama Wave-2'de "5-sağlayıcı çeşitliliği" iddiası pratikte tek sağlayıcıya iner; bu dürüstçe belgelenir (sahte-çeşitlilik illüzyonu bırakılmaz).

## Alternatifler + D1 araştırması
- **(a) OpenRouter fallback (Wave-3 en güçlü aday, D1 araştırıldı):** birleşik router, 300+ model, tek API key. Ücretsiz katman 20+ model (Llama 3.3 70B, GPT-OSS 120B, Qwen3) — kritik: ücretsiz katman **istek-bazlı (50/gün, 20/dk), TPM-bazlı DEĞİL** → Groq/Cerebras'ın 8000-TPM darboğazını aşan zengin koç prompt'unu servis edebilir. Murat'ın düşük çağrı hacmi 50/gün'e sığar. Fallback-faturalama (yalnız başarılı çağrı). PAYG'de %5.5 platform ücreti.
- **(b) Anthropic ücretli (Wave-3):** en yüksek kalite; Murat'ın Anthropic kredisi yok (eval denemesinde "credit too low"). Günde 50+ koç çağrısı kalite farkını gerçek hissettiğinde mantıklı (Wave-3 backlog C1).
- **(c) Yerel Ollama (LLM-005, mevcut):** egemen/offline; kalite kabul edilebilirlik testi Wave-3.

## Revize tetikleyicisi
Groq/Cerebras kotaları düzelirse VEYA OpenRouter (Llama 3.3 70B) canlı kalite+latency+TR-erişim testi geçerse → fallback zincirine OpenRouter eklenir (ADR-034 Wave-3). Şu an: `LLM_PROVIDER=fallback` zinciri korunur, Gemini birincil.
