# ADR-023 — Wave-2 H2G4-G7 sıra değişikliği (veri-gerçeklik uyumu)

**Tarih:** 16 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-001, ADR-024, ADR-025

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Plan v3 sırası H2G4'te Anomaly+Pattern+Recurring Detection istiyordu. Ama `transaction`=0 (sistem henüz kullanılmıyor) → anomaly detector boş çalışır, canlı test edilemez, sıfır somut değer.

## Karar
Sıra değişikliği: H2G4 → **Debt Strategy Engine** (eski G7), H2G5 → **Goal Engine** (eski G6), H2G6 → Proaktif Brief (eski G5), H2G7 → Anomaly+Recurring Detection (eski G4, veya Wave-3'e ertelenir).

## Alternatifler (reddedildi)
- A) Plan'a tam sadık (transaction=0 ile anomaly yazmak — dormant kalır).
- B) `setup_data.py` ile mock 30 gün transaction — Decision Journal + CoachInsight gerçek olmayan veriyle kirlenir (memory disiplini ihlali).

## Gerekçe
- Sektör (NerdWallet/US News 2026): "MVP 5-7 core feature; anomaly detection mature-data feature, Day 1 değil." YNAB "Plan ahead, don't track past."
- D1 BENİ DÜŞÜN: net değer −22.274 TL, 2 Garanti kredisi, kart %99. En acil ihtiyaç debt strategy + goal engine. Transaction=0 → anomaly boş çalışır, yanlış sinyal.
- ADR-001 ilkesinin saf uygulaması: Snowball/Avalanche deterministik matematik, LLM gerekmez.
- Memory disiplini: mock transaction (opsiyon B) reddedildi — Decision Journal/CoachInsight sahte veriyle kirlenir.

## Revize tetikleyicisi
30+ gün transaction birikince H2G7 (anomaly+recurring) Wave-2 H4 polish'ine eklenir veya Wave-3'e taşınır.

## Kaynak
MCP `adr_log` [16 Mayıs 2026], transaction count=0 keşfi.
