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

## Revize (14 Tem 2026) — EVDS v2 → v3 geçişi (M19 regression fix)
TCMB EVDS **v3'e taşındı**; eski `evds2.tcmb.gov.tr/service/evds/` 405/SPA döndürüyordu.
- **Base URL:** `https://evds3.tcmb.gov.tr/igmevdsms-dis` (v2 deprecated ~May 2026).
- **Format:** `{base}/series=<KOD-KOD>&startDate=<gg-aa-yyyy>&endDate=<gg-aa-yyyy>&type=json`
  (series PATH'e gömülü, çoklu seri tire ile).
- **Auth:** HTTP header `{"key": EVDS_API_KEY}` (query-param DEĞİL; iletmeyene 403).
- **Seri kodları KORUNDU:** TP.DK.USD.A/.S (döviz alış/satış), TP.MK.F.BILESIK.TUM (altın bileşik-fon endeksi).
- **Response:** noktalar `_` olur (TP.DK.USD.A → TP_DK_USD_A); değer string/null (hafta sonu).
- **Kanıt (canlı 14 Tem):** USD alış 46.9121 / satış 46.9966 (14-07-2026). ✅
- **R3 not:** `TP.MK.F.BILESIK.TUM` bileşik-fon endeksi (73804) döner — **gram-altın-TL değil**;
  gram-gold ayrı seri gerektirir (Wave-4).
- Kod: `app/price_providers/evds_client.py` (fetch_series/fetch_currency_rate/fetch_gold_price +
  get_evds_price compat). Kaynak: EVDS Web Servis + Python Kılavuzu PDF (Murat 14 Tem).

## Revize (18 Tem 2026, M-hisse / Wave-7) — BIST hisse otomasyonu CANLI
`try_auto_fetch_stock_price` STUB'dı ('V2'de aktive edilecek', None dönüyordu) → **İş Yatırım HisseTekil JSON** endpoint'iyle gerçek implementasyona alındı. Zincir: yfinance (bu ortamda Yahoo-blok → None) → **İş Yatırım fallback** (`HGDG_KAPANIS` son kapanış). CANLI doğrulandı: THYAO=329.50, ASELS=351.50, GARAN=126.80. Uçtan uca KULLANIM-GATE: gerçek THYAO hesabı → `fetch_for_account` → PriceHistory `isyatirim` satırı → cockpit `yatirim_deger`. Okuma önceliği güncel: manual > tefas > yfinance > **isyatirim** (BIST fiili birincil, yfinance blok nedeniyle). Test: `tests/test_stock_price_isyatirim_m_hisse.py` (mock, ağ-bağımsız).
