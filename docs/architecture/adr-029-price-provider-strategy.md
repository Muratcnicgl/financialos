# ADR-029 — Fiyat sağlayıcı stratejisi (otomatik fiyat çekimi)

**Tarih:** 12 Temmuz 2026 · **Durum:** Kabul edildi (M4) · **İlgili:** ADR-012 (PriceHistory kompozit PK), Improvement Backlog #028 (8 May 2026'dan açık)

## Bağlam
TLY fonu + gelecekteki BIST/altın/döviz fiyatları elle güncelleniyordu (#028). Otomatik çekim gerekli. **R3 GERÇEĞİ (M4 tanılama — charter varsayımını düzeltti):**
- Sağlayıcı paketleri (borsapy 0.8.7, pytefas 0.3.0, tefas-crawler 0.5.0, yfinance 0.2.48) **zaten kuruluydu.**
- `fund_tracker.try_auto_fetch_fund_price` **zaten çalışıyordu** (pytefas, canlı TLY=7277.90) — "placeholder" değildi.
- **Eksik olan:** çalışan fetch bir scheduler cron'una bağlı değildi + `PriceHistory` yazılmıyordu + `app/price_providers/` modülü (PriceHistory docstring'inin atıf yaptığı) HİÇ kurulmamıştı.
- **Sağlayıcı testi (D1):** pytefas ÇALIŞIR (funds). **borsapy TEFAS API 404** (`GetAllFundAnalyzeData`) — charter'ın "borsapy birincil" premisi R3 ile REDDEDİLDİ. tefas-crawler sonuçsuz. yfinance BIST `currentTradingPeriod` KeyError.

## Karar
- **Fon (fund) birincil sağlayıcı: pytefas / TEFAS** (tek çalışan, kanıtlı). Fallback: yok (diğerleri şu an kırık); graceful None → elle giriş.
- **`app/price_providers/router.py`** kuruldu (modelin atıf yaptığı yer): `get_fund_price` (pytefas reuse) + `get_stock_price` (İş Yatırım, gelecek BIST) + `fetch_for_account` (dispatch) + 4-saat TTL cache (Murat'ın 2 TLY hesabı tek çağrıya iner) + `record_investment_price` (PriceHistory kompozit-PK idempotent + current_price denormalize cache).
- **APScheduler cron `fetch_investment_prices` — gece 02:45** (nightly_batch 03:00 ÖNCESİ → batch/cockpit taze fiyat kullanır). Tüm `investment` hesapları.
- **PriceSource önceliği** (okuma): manual > tefas > yfinance > isyatirim.

## Alternatifler (reddedildi)
- borsapy birincil (charter önerisi) → TEFAS API 404, çalışmıyor.
- Selenium/Playwright TEFAS scraping → yavaş/kırılgan, pytefas JSON API varken gereksiz.
- Elle giriş → #028'in çözmek istediği sorun.

## Revize tetikleyicisi
BIST/altın/döviz eklendiğinde (Wave-3 multi-asset, ADR-031) stock/fx sağlayıcıları aktive edilir (İş Yatırım hisse D1'de çalışmıştı; TCMB EVDS döviz; CoinGecko kripto). pytefas bakımı bırakılırsa borsapy/tefas-crawler yeniden değerlendirilir.

## Doğrulama
Canlı: `fetch_investment_prices_job` → TLY=7277.90 (pytefas/tefas), 2/2 hesap current_price güncellendi (stale 4929→7277), PriceHistory'ye satır (TLY 2026-07-12 tefas). Cache tek çağrıya indirdi.
