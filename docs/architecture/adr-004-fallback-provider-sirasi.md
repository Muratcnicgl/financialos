# ADR-004 — FallbackProvider sıralaması

**Tarih:** 2 Mayıs 2026 · **Durum:** Kabul edildi (ADR-034 ile revize edildi) · **İlgili:** ADR-002, ADR-034

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Fallback zincirinde hangi sağlayıcının önce denendiği, talimat-takibi kalitesini ve kota davranışını belirler.

## Karar (2 Mayıs 2026)
Sıra: **Groq → Cerebras → Gemini → OpenRouter**.

## Alternatifler (reddedildi)
- Groq → Gemini sırası.

## Gerekçe
Llama 3.3 70B (Groq) daha iyi talimat takibi gösterdi (BUG #022 öğretti).

## Revize
**ADR-034 (Wave-3 M13, 13 Tem 2026)** zinciri yeniden düzenledi: Gemini (birincil, TR+kalite) → OpenRouter → Cerebras → Together → DeepInfra → Groq (TPM 8000 sınırlı, sona) → Ollama (egemen offline son çare). Bu ADR'nin orijinal sırası artık geçerli değil.

## Kaynak
MCP `adr_log` [2 Mayıs 2026], revize [13 Tem 2026 ADR-034].
