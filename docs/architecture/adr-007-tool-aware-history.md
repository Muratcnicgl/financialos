# ADR-007 — Tool-aware history (CoachMemory tool kolonları)

**Tarih:** 6 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** BUG #036

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Sohbet geçmişinde araç çağrıları (propose_action) yeniden oynatılırken kayboluyordu (BUG #036) — LLM'e verilen geçmiş tutarsızdı.

## Karar
`CoachMemory` tablosuna **`tool_calls_json` + `tool_call_id`** kolonları eklendi — araç çağrıları yapısal olarak saklanır.

## Alternatifler (reddedildi)
- Placeholder fallback (3 fix denendi, başarısız).

## Gerekçe
Yapısal fix tek doğru yol — placeholder yamaları geçmişi bozuyordu.

## Kaynak
MCP `adr_log` [6 Mayıs 2026]. Uygulama: `app/models.py` (CoachMemory).
