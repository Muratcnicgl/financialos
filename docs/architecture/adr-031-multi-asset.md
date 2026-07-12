# ADR-031 — Multi-asset (kripto/hisse/döviz/altın/gayrimenkul)

**Tarih:** 13 Tem 2026 · **Durum:** 🟡 TASLAK — karar Wave-3 başında (M7 hazırlık, KARAR YOK) · **İlgili:** ADR-019 (multi-asset vizyon), ADR-030 (Numeric revize-tetiği), price_providers

## Bağlam
Wave-2 yalnız TEFAS fonu (Account.fund_code). `app/price_providers/` dispatch-hazır (get_stock_price İş Yatırım stub). Multi-asset = varlık modelini + fiyat sağlayıcı zincirini genişletme.

## Açık Sorular (KARAR BEKLİYOR)
1. **Model:** tek `Account` + `asset_type` kolonu mu, varlık-sınıfı başına ayrı tablo mı? (esneklik vs normalizasyon)
2. **Fiyat sağlayıcı:** kripto→CoinGecko? hisse→İş Yatırım (D1'de çalıştı)? döviz→TCMB EVDS? altın→? — her biri D1 + rate-limit.
3. **Hassasiyet:** kripto için `Numeric(19,4)` yetersiz → `Numeric(28,8)`? (ADR-030 revize-tetiği; satoshi 8 ondalık).
4. **Emanet (MC1):** çoklu-varlıkta dokunulmaz-emanet nasıl işaretlenir?
5. **K/Z:** varlık-sınıfı bazlı maliyet/stopaj (kripto vergi TR? hisse stopaj?).

## D1 (Wave-3'te yapılacak) → Research Log
CoinGecko/Binance API, TCMB EVDS döviz, muhasebe multi-asset modelleri (Beancount commodities, Firefly asset-classes).

## Karar
**(BOŞ — Wave-3 başında D1 sonrası.)**

## Kaynak
ADR-019, wave-3-master-plan.md §1, price_providers dispatch mimarisi.
