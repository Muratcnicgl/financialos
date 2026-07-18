# ADR-014 — Fiyat geçmişi backfill aralığı: 1 yıl (initial)

**Tarih:** 9 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-012, ADR-015

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
`PriceHistory` backfill'inin ne kadar geriye gideceği, getiri metriklerinin (TWR/MWR/IRR) anlamlılığını belirler.

## Karar
`scripts/backfill_price_history.py` default `--start = bugün − 365 gün`, `--end = bugün`. Argparse ile override edilebilir (ileride 3/5 yıla genişletme tek komut).

## Alternatifler (reddedildi)
- A) 6 ay — annualization eşiği altında, TWR/MWR anlamsız.
- C) 3 yıl — gereksiz veri, MVP için fazla.
- D) Tüm geçmiş (TEFAS 2007'ye kadar) — aşırı.

## Gerekçe
5/5 sektör referansı 1 yıl default kullanıyor (Portfolio Performance, Sharesight "<1 yıl annualization yapılmaz", Schwab/Vanguard, Portfolio Visualizer). TWR/MWR/IRR matematiksel olarak ≥1 yıl gerektirir. pytefas tek çağrıda 365 gün döner (rate-limit sorunu yok).

## Revize tetikleyicisi
Sharesight tarzı çok-dönemli rapor (1/3/5 yıl karşılaştırma) eklenirse `--start` geriye taşınır.

## Kaynak
MCP `adr_log` [9 Mayıs 2026] + Research Log.
