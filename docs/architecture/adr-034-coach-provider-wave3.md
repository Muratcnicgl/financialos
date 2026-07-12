# ADR-034 — Koç sağlayıcı Wave-3 (ADR-028 revize + sub-agent routing)

**Tarih:** 13 Tem 2026 · **Durum:** 🟡 TASLAK — karar Wave-3 başında (M7 hazırlık, KARAR YOK) · **İlgili:** ADR-028 (fiilen Gemini-only), research-log OpenRouter D1, wave3-vision §1

## Bağlam
ADR-028: koç fiilen Gemini (Groq/Cerebras TPM eler). Wave-3: (a) sağlayıcı çeşitliliği (OpenRouter fallback), (b) sub-agent routing (tek mega-prompt → intent classifier + uzman ajanlar, wave3-vision §1). P1-25 ile Anthropic artık tool-aware.

## Açık Sorular (KARAR BEKLİYOR)
1. **Routing:** LangGraph state machine mi, hafif kendi intent-router mı? (bağımlılık vs kontrol).
2. **OpenRouter:** canlı fallback testi (research-log: 50/gün, TPM-sınırsız) — birincil mi, yalnız fallback mı?
3. **Intent classifier:** küçük-model maliyeti (kahve vs TLY-analizi ayrımı) değer üretir mi?
4. **Prompt caching** (P2-13): system prompt cache → maliyet.
5. **Uzman ajanlar:** bildirim/soru-cevap/analiz/hatırlatma ayrımı (ADR-001 "Rules Engine karar verir" korunur — ajanlar açıklar).

## D1 (Wave-3'te yapılacak) → Research Log
LangGraph vs custom router, OpenRouter canlı, intent-classification maliyet/fayda, prompt caching (Anthropic/Gemini).

## Karar
**(BOŞ — Wave-3 başında D1 sonrası.)**

## Kaynak
ADR-028, research-log.md, wave3-vision.md §1, wave-3-master-plan.md §4.
