# ADR-019 — Wave-3 Multi-Asset Vizyonu

**Tarih:** 9 Mayıs 2026 (11 May re-create) · **Durum:** Kabul edildi (vizyon) → ADR-031 ile uygulamaya bağlandı · **İlgili:** ADR-031

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Sadece TEFAS fonu, Türkiye kullanıcısının tipik portföyünün (BIST hisse + altın + döviz + crypto + gayrimenkul) yarısını görmez.

## Karar (vizyon — schema Wave-3'te netleşti)
Wave-3'te multi-asset balance sheet (Kubera/Sharesight paterni). Türkiye-özgü kapsam: BIST hisse, altın (gram/ons), crypto (BTC/ETH), döviz (USD/EUR), gayrimenkul (manuel).

**Schema seçenekleri (Wave-3 ADR-031'de karara bağlandı):**
- A) Account STI — account_type discriminator + tip-spesifik kolonlar (NULL-heavy, tek tablo; Empower/Monarch).
- B) Ayrı Holdings tablosu (asset_type STI); Account yalnız para hesapları (Sharesight/Quantstart).

**Sağlayıcılar:** yfinance (BIST + altın + döviz), CoinGecko (crypto), TCMB EVDS (resmi döviz), pytefas (TEFAS), Manuel (gayrimenkul).

**Sıra:** InvestmentTransaction (lot history) → BIST hisse → altın → döviz → crypto → gayrimenkul.

## Alternatifler (reddedildi)
- A) Sadece TEFAS (kullanıcı hayatının yarısını görmez).

## Gerekçe
6 sektör referansı (Kubera, Empower, Monarch, Sharesight, Portfolio Performance, Exirio) multi-asset balance sheet kullanıyor. YAGNI/Rule of Three: schema 3. asset tipi gelirken yapıldı.

## Revize / uygulama
**ADR-031 (Wave-3 M12, 13 Tem 2026)** schema kararını verdi: tek Account + `asset_type` kolonu (STI seçeneği A). Kripto Wave-4'e ertelendi.

## Kaynak
MCP `adr_log` [9 Mayıs 2026, 11 May re-create]. Not: 11 May Working State temizliğinde silinip conversation_search ile geri kazanıldı.
