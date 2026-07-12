# ADR-012 — PriceHistory kompozit PK + çoklu-kaynak

**Tarih:** Wave-2 B4 · **Durum:** Kabul edildi · **Kaynak:** `app/models.py` (PriceHistory), `app/price_providers/` (Wave-2 M4)

## Bağlam
Yatırım fiyat geçmişi birden çok kaynaktan gelebilir (manuel, TEFAS, yfinance, İş Yatırım). Aynı fon+gün için farklı kaynaklardan fiyat gelebilir; hangisinin geçerli olduğu ve idempotent yazım gerekir.

## Karar
`PriceHistory` **kompozit birincil anahtar: (fund_code, price_date, source)**. Kaynak (`PriceSource` enum) okuma önceliği: manual > tefas > yfinance > isyatirim. Aynı (fund_code, price_date, source) tekrar yazımı idempotent (kompozit PK duplicate'i engeller).

## Sonuç
- Çoklu-kaynak fiyat çekimi (M4 fiyat otomasyonu) duplicate üretmeden çalışır.
- Kaynak önceliğiyle "en güvenilir" fiyat okunur.
