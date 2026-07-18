# ADR-017 — Coach Insights iki tip dormant sweep (sabit vs dinamik küme)

**Tarih:** 10 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-016

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Bir insight "aktif" iken karşıt kanıt gelince "dormant"a indirilmeli. Ama bazı insight kümeleri sabit (MC1-8, OARS metrikleri), bazıları kullanıcıya bağlı dinamik (kategori adları).

## Karar
İki tip dormant transition:
- **Sabit küme** — `_upsert_insight_absolute` içindeki dormant: sabit liste (MC1-8, OARS 4 metrik) her çağrıda hepsi yazılır, biri active diğeri dormant.
- **Dinamik küme** — manuel SWEEP pass: önce aktif olması gerekenler yazılır, sonra DB'deki tüm kayıtlar taranıp "aktif olması gerekenler" dışındakiler dormant'a indirilir.

## Alternatifler (reddedildi)
- A) Tek tip dormant (hepsi sabit varsayılır) — dinamik insight'lar için yanlış.
- B) Hep manuel sweep — sabit küme için gereksiz DB tarama.

## Kullanım kuralı
Sonraki extractor'lar: action_rejection_pattern DİNAMİK (action_type'a göre), breakthrough/setback dinamik, explicit_red_line dinamik.

## Revize tetikleyicisi
Dormant transition kriterleri (90 gün, counter_evidence threshold) değişirse.

## Kaynak
MCP `adr_log` [10 Mayıs 2026], commit 305f975.
