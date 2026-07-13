# ADR-031 — Multi-asset (kripto/hisse/döviz/altın/gayrimenkul)

**Tarih:** 13 Tem 2026 · **Durum:** ✅ KARAR VERİLDİ (Wave-3 M12, D1 + K10) · **İlgili:** ADR-019 (multi-asset vizyon), ADR-030 (Numeric revize-tetiği), price_providers

## Bağlam
Wave-2 yalnız TEFAS fonu (`Account.fund_code`). `app/price_providers/router.py` dispatch-hazır (`get_stock_price` stub). Multi-asset = varlık modelini + fiyat sağlayıcı zincirini genişletme.

## D1 — Sektör Referansları

| Proje | Multi-asset modeli | Fiyat kaynağı |
|-------|--------------------|---------------|
| **Beancount** | `commodities` — tek defter, her varlık bir "commodity" (USD, AAPL, BTC), fiyat `price` direktifi | manuel/harici besleme |
| **Firefly III** | asset-account tipleri + para birimi; yatırım sınırlı | manuel |
| **Maybe Finance** | `Security` + `Holding` + `Trade` tabloları (hisse/fon), `Account` polymorphic | Synth/market-data provider |
| **yfinance** | — | BIST (`.IS` suffix) + global hisse, ücretsiz, key yok |
| **TCMB EVDS** | — | resmi döviz + altın kuru, **API key gerekli** (ücretsiz kayıt) |
| **CoinGecko** | — | kripto, free tier key'siz çalışır |

**Çıkarım:** Beancount'un "commodity" modeli en zarif: tek tablo + tip. Bizim `Account`'a **`asset_type` discriminator** eklemek (fund/stock/gold/fx/crypto), `fund_code`'u genel `symbol` gibi kullanmak — ayrı tablo (Maybe tarzı Security/Holding) MVP için fazla normalizasyon. Fiyat: her varlık sınıfı için ayrı provider (yfinance/EVDS/CoinGecko), mevcut pytefas fon için kalır.

## K10 — Üç Boyut

- **MUHAKEME:** Tek-tablo + `asset_type` = az migration, mevcut `lot_count`/`current_price`/`PriceHistory` yeniden kullanılır. Provider dispatch zaten var (`fetch_for_account`). yfinance BIST'i key'siz çeker (D1 kanıtı gerekli), CoinGecko free key'siz, EVDS key ister (API_KEY_TALEP).
- **BENİ DÜŞÜN (Murat):** Şu an TLY fonu var. BIST hisse + altın + döviz gerçekçi sonraki adım (öğrenci portföyü). Kripto **opsiyonel** — 8-ondalık hassasiyet (satoshi) mevcut Numeric(19,4)'e sığmaz → ayrı migration riski. Öğrenci bütçesinde EVDS ücretsiz.
- **GENELİ DÜŞÜN (TR):** TR yatırımcısı BIST + altın + döviz ağırlıklı. EVDS resmi TCMB kaynağı (güvenilir, KVKK-uyumlu yurt-içi). Kripto TR'de yaygın ama vergi/regülasyon belirsiz → dikkatli.

## Karar

1. **Model:** Tek `Account` + **`asset_type`** kolonu (`fund`|`stock`|`gold`|`fx`|`crypto`). `fund_code` genel sembol olarak kullanılır (TLY, THYAO.IS, XAUUSD, USDTRY, BTC). PriceHistory `fund_code` PK'si sembol olur (şema değişmez).
2. **Hassasiyet:** **BIST/altın/döviz → mevcut `Numeric(19,4)` yeterli** (fiyatlar makul ölçekte). **Kripto → `Numeric(28,8)` gerekir (satoshi 8 ondalık)** — bu para-kolonları migration'ı ADR-030 revize-tetiği; **KARAR: kripto Wave-4'e ertelendi** (risk/regülasyon + geniş migration). M12 kapsamı: **stock + gold + fx**.
3. **Sağlayıcılar:** `yfinance` (BIST `.IS` + global hisse, key'siz) · `TCMB EVDS` (döviz + altın, **API_KEY_TALEP**) · pytefas (fon, mevcut). CoinGecko (kripto) → Wave-4.
4. **Emanet (MC1):** `is_emanet`/checkpoint mekanizması varlık-tipinden bağımsız çalışır (Account seviyesinde) — değişiklik gerekmez.
5. **K/Z + vergi:** cost-basis (`purchase_price`/`lot_count`) mevcut; stopaj/vergi hesabı **rules_engine** işi (Wave-4, TR hisse stopaj + fon vergi kuralları netleşince).
6. **Backfill:** `scripts/backfill_prices_all_accounts.py` (mevcut) yeni asset_type'ları kapsayacak şekilde genişletilir.

## Uygulama (M12)
`Account.asset_type` + migration · `price_providers/` yeni client'lar (yfinance_client, evds_client) + router dispatch asset_type'a göre · backfill · frontend Accounts asset-type seçimi · testler (mock + gerçek).

## Kaynak
ADR-019, wave-3-master-plan.md §1, ADR-030 (Numeric revize), price_providers dispatch, D1 (Beancount commodities / Maybe Security-Holding / yfinance / EVDS / CoinGecko).
