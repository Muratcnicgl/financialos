# ADR-016 — Coach Insights iki helper paterni (olay-tepki vs eşik-tepki)

**Tarih:** 10 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-006, ADR-017

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Coach insight extractor'ları iki farklı doğaya sahip: olay-tetikli (anlık) ve periyodik (günlük tarama). Tek helper her ikisini de temiz karşılayamıyor.

## Karar
İki ayrı helper:
- **`_save_or_update_insight`** — olay-tetikli extractor'lar (decision_rhythm, action_rejection_pattern, explicit_red_line K1). `evidence_count` INCREMENTAL (+1), status hep `active`.
- **`_upsert_insight_absolute`** — periyodik extractor'lar (mc_reference_frequency, question_typology, category_account_preference, breakthrough, setback, explicit_red_line K2). `evidence_count` MUTLAK, status parametre (active/dormant/invalidated).

## Alternatifler (reddedildi)
- A) Tek genel helper (mode switch) — karmaşık, semantik belirsiz.
- B) Her extractor kendi DB çağrısı — DRY ihlali, race-condition koruması kaybolur.

## Gerekçe
mc_reference_frequency'de dominant_mc testi `_save_or_update_insight` ile fail oldu (incremental + zorla-active mantığı periyodik paterni bozdu). İki helper'ı ayrı tutmak hem semantik netlik hem gelecek refactor kolaylığı.

## Revize tetikleyicisi
Sonraki extractor'larda 3. bir desen ortaya çıkarsa 3. helper veya factory pattern.

## Kaynak
MCP `adr_log` [10 Mayıs 2026], commit 90bd628.
