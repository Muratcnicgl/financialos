# ADR-006 — Wave-2 mimari üçgeni (öğrenen koç)

**Tarih:** 6 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-001, ADR-016, ADR-017, ADR-020

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Wave-1 koçu durumsuz (stateless) bir açıklayıcıydı — geçmiş sohbetten öğrenmiyordu. Kalıcı davranışsal hafıza gerekliydi.

## Karar
**CoachInsight + reflection hook + rolling pattern** üçlüsü ile durumsuz açıklayıcıdan öğrenen koça geçiş. ADR-001 mimarisi ("Rules Engine karar verir, LLM açıklar") 4 katmana çıkarıldı:
1. Deterministik snapshot (rules_engine cockpit),
2. Schema-garantili eylem (propose_action → PendingAction),
3. Arka plan reflection (extractor'lar),
4. Kalıcı insight memory (CoachInsight).

## Alternatifler (reddedildi)
- Mevcut Wave-1 sistemi (yetersiz — öğrenme yok).

## Gerekçe
ADR-001 ilkesi bozulmadan koça hafıza eklendi: matematik hâlâ deterministik, LLM hâlâ yalnız açıklıyor; öğrenme ayrı katmanda.

## Kaynak
MCP `adr_log` [6 Mayıs 2026].
