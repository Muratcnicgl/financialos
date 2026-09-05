# ADR-018 — Wave-2 H1G3 ReAct Reasoning Layer (UX + retention kararları)

**Tarih:** 10-11 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-006

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Koçun muhakeme adımlarını (ReAct trace) kullanıcıya göstermek için UX + veri retention kararları gerekti. Sektör 8+ kaynak tarandı (LangSmith, assistant-ui, asistan Extended Thinking, ChatGPT Thinking, Perplexity, Langfuse, LandingAI ADE, OWASP).

## Karar (8 alt karar)
1. **Operation type renk:** 5 ayrı renk yerine tek muted ton + Lucide ikon + Türkçe etiket. Vurgu yalnız final_answer (indigo) ve step.error (kırmızı).
2. **Confidence badge eşikleri:** ≥0.80 yüksek/yeşil, 0.50-0.79 orta/amber, <0.50 düşük/kırmızı.
3. **Confidence tooltip:** "göreceli sinyal, mutlak güvenilirlik değil" + "benefit + boundary, no blame".
4. **Default collapsed + lazy fetch** on first open.
5. **404 yolu:** yetkisiz erişim ve trace-yok her ikisi de 404 (resource hiding, OWASP).
6. **Cleanup retention 90 gün** (Langfuse warm-tier konvansiyonu).
7. **Cleanup job 04:00 Istanbul** (03:00 nightly + 03:30 k2'den sonra, SQLite write-lock contention önleme).
8. **SQLAlchemy 2.x bulk delete** + index'li created_at + strict less-than boundary.

## Alternatifler (reddedildi)
- 5-renk operation type; daha sık retention (30g — trend analizi yetersiz).

## Gerekçe
Sektör 8+ kaynak konsensüsü.

## Revize tetikleyicisi
Production'da farklı UX feedback veya storage koşulları değişirse.

## Kaynak
MCP `adr_log` [10-11 Mayıs 2026], commit faf631d→9d03ce5.
