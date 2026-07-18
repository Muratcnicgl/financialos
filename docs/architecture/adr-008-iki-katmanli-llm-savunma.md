# ADR-008 — İki katmanlı LLM savunma (input + output)

**Tarih:** 6 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** BUG #033, ADR-005

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Stokastik LLM davranışı yalnız prompt talimatıyla güvenilir biçimde sınırlanamıyor (BUG #033 gösterdi).

## Karar
İki katmanlı savunma: **prompt katmanı (input) + post-process regex (output)**. LLM çıktısı deterministik bir son-işlem katmanından geçer.

## Alternatifler (reddedildi)
- Sadece prompt savunması — BUG #033 paterni yetersiz olduğunu kanıtladı.

## Gerekçe
Stokastik LLM davranışı için deterministik post-process katmanı sektör standardıdır (yalnız prompt'a güvenilmez, ADR-001 ruhu).

## Kaynak
MCP `adr_log` [6 Mayıs 2026].
