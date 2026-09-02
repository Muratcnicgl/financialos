# ADR-002 — Provider-agnostic LLM mimarisi (fallback zinciri)

**Tarih:** 30 Nisan 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-004 (fallback sırası), ADR-028 (SUPERSEDED), ADR-034 (revize)

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`. 2 aydır yalnız MCP'deydi (ADR envanteri boşluğu; materyalizasyon M74'te tamamlandı).

## Bağlam
Tek bir LLM sağlayıcısına kilitlenmek, ücretsiz katman (free tier) kota/limitleri altında koçu kırılgan yapar. Bir sağlayıcı 429/quota dolduğunda sistem durmamalı.

## Karar
`LLMProvider` soyut sınıfı + sağlayıcı adapter'ları: `AnthropicProvider` + `GeminiProvider` + `GroqProvider` + `CerebrasProvider` + `OpenRouterProvider` (+ sonradan Together/DeepInfra/Ollama). `FallbackProvider` zinciri birincil 429/quota/boş-cevap'ta bir sonrakine geçer.

## Alternatifler (reddedildi)
- Tek sağlayıcıya kilitlenmek → free tier limitlerinde kırılgan.

## Gerekçe
Free tier limitleri için fallback şart. Adapter deseni yeni sağlayıcı eklemeyi tek sınıfa indirger.

## Revize tetikleyicisi
Tek sağlayıcı (ör. ücretli Anthropic) tek başına yeterli/güvenilir olursa zincir sadeleşebilir.

## Kaynak
MCP `adr_log` [30 Nisan 2026]. Uygulama: `app/coach.py` (LLMProvider + FallbackProvider).
