# ADR-005 — `is_question()` deterministik ön-sınıflandırıcı

**Tarih:** 3 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-001 (Rules Engine karar verir, LLM açıklar)

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Kullanıcının mesajı bir **soru/analiz talebi** mi yoksa **gerçekleşmiş bir eylem bildirimi** mi ayrımı KURAL SIFIR'ın temelidir (propose_action yalnız bildirimde çağrılır). Bu ayrımı LLM'e bırakmak sağlayıcıdan sağlayıcıya değişen davranış üretir.

## Karar
Soru/bildirim ön-sınıflandırması **kod seviyesinde deterministik** yapılır (`is_question()`), LLM'e bırakılmaz.

## Alternatifler (reddedildi)
- LLM'e güvenmek — BUG #023 paterni (sağlayıcı farkı + stokastik davranış).

## Gerekçe
Soru/bildirim ayrımı kod seviyesinde olunca sağlayıcı farkı kapatılır, KURAL SIFIR ihlali önlenir.

## Kaynak
MCP `adr_log` [3 Mayıs 2026].
