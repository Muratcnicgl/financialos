# ADR-022 — 3-Ufuklu Karar Masası (T+0 / T+30 / T+90)

**Tarih:** 16 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-019, ADR-024, Improvement #022

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Plan v3 "Bugün / 3 ay / 3 yıl" karar masası istiyordu. 3 yıl (1095 gün) projeksiyonu, TLY fiyatının 3 yıl sabit varsayılmasını gerektirir — TR enflasyon belirsizliğinde yanıltıcı.

## Karar
`simulation_engine.simulate_action` **`horizons_days=(0, 30, 90)`** ile çağrılır. `POST /api/simulate/{action_id}` üçünü birden döner. **3 yıl (T+1095) Wave-3'e ertelendi.**

## Alternatifler (reddedildi)
- A) Literal 1095 gün — engine destekliyor ama TLY fiyat sabit + enflasyon modelsiz + drift birikir → halüsinasyon yüksek.
- C) Kullanıcı gün seçsin toggle — YAGNI.

## Gerekçe
- Improvement #022 orijinali "T+0/T+30/T+90" (1 May 2026).
- D1 BENİ DÜŞÜN: TR enflasyon belirsizliği (USD-TL %30-50 yıllık volatilite), TLY 3 yıl sabit varsayılamaz.
- Sektör (McKinsey 3 Horizons 2026): "Horizons takvim kutusu değildir." Engine kapasitesine sadık kalmak D1 "pivot to evidence" kuralına uygun.

## Revize tetikleyicisi
Wave-3 multi-asset (ADR-019) + enflasyon-aware projeksiyon olunca T+1095 eklenir.

## Kaynak
MCP `adr_log` [16 Mayıs 2026], Plan v3 H2G3.
