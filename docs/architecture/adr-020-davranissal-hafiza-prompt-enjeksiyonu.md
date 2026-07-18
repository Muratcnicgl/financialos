# ADR-020 — Davranışsal hafıza prompt enjeksiyonu (Wave-2 yapısı)

**Tarih:** 13 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-006, ADR-016

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
CoachInsight'lar LLM prompt'una nasıl enjekte edilecek? Tümünü koymak prompt'u şişirir ("lost-in-the-middle"), özetlemek severity'yi bozar.

## Karar
`app/coach_insights.py`'a `format_insights_for_prompt(db, user_id, max_tokens=1500)`:
- **Filtre:** `status='active'` (dormant/invalidated dahil değil).
- **Sıralama:** `sort_priority DESC NULLS LAST, last_evidence_at DESC NULLS LAST`.
- **Limit:** Top 5.
- **Token budget:** 1500 hard cap (tiktoken cl100k_base, fallback len/4).
- **Strateji:** DROP > truncate > summarize (2026 standardı).
- **Format:** structured `[INSIGHT_TYPE | GÜVEN: confidence_basis]` etiketli.
- **Konum:** `coach.py._build_context_message()` içinde, davranış kalıpları bloğundan sonra.

## Alternatifler (reddedildi)
- A) Tüm aktif insight'lar — şişmeli prompt, lost-in-the-middle.
- B) Top-5 + içerik truncate — summarization severity'yi düzler (JetBrains 2026), verbatim +20pp accuracy (arxiv 2605.04897).
- C) System message'a ekleme — caching yararı ama dinamizm kaybı.

## Gerekçe
5 sektör referansı: Mem0 LOCOMO (selective retrieval %26 doğruluk %90 token tasarrufu), Letta core memory, OpenAI Realtime "Use structure", arxiv 2605.04897 (Storage Is Not Memory), JetBrains 2026 anti-sycophancy.

## Revize tetikleyicisi
6 hafta gerçek kullanım sonrası: içerik özetleme katmanı / top-K dinamikleşme / dormant otobiyografi / user_invalidated mini-bölüm.

## Kaynak
MCP `adr_log` [13 Mayıs 2026], commit 3d5f8cb.
