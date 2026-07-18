# ADR-003 — İki net değer metriği (Görülen vs Tam)

**Tarih:** 2 Mayıs 2026 · **Durum:** Kabul edildi

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Operasyonel karar ile stratejik karar farklı rakamlara bakar. Tek bir "net değer" sayısı bu iki bakışı bulanıklaştırır.

## Karar
İki ayrı metrik:
- **Görülen Net Değer** — alacaksız (MC8 "önce hayatta kal" ruhuna uygun, operasyonel).
- **Tam Net Değer** — alacaklı (sözleşmeli tahsilat takvimi dahil, stratejik).

## Alternatifler (reddedildi)
- A) Konservatif (yalnız nakit) — stratejik resmi gizler.
- B) Tek "tam tablo" (alacak dahil) — operasyonel likidite yanılsaması yaratır.

## Gerekçe
Operasyonel vs stratejik karar farklı rakamlara bakar; realist koç bunu ayırır. Cockpit her ikisini de döner (`net_deger` görülen, `net_deger_tam` alacaklı).

## Kaynak
MCP `adr_log` [2 Mayıs 2026]. Uygulama: `app/rules_engine.py` (generate_cockpit).
