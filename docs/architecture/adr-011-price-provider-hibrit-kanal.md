# ADR-011 — PRICE_PROVIDER hibrit kanal stratejisi

**Tarih:** 8 Mayıs 2026 · **Durum:** Kabul edildi (ADR-029 ile güncellendi) · **İlgili:** ADR-012, ADR-029, ADR-031

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Farklı varlık sınıfları (TEFAS fonu, BIST hisse, altın, döviz) farklı fiyat kaynakları gerektirir; tek sağlayıcı hepsini karşılamaz.

## Karar
Hibrit kanal:
- **TEFAS fonu:** `pytefas==0.3.0` (resmi 2026 JSON API, HTML scraping yok).
- **BIST hisse + altın + döviz:** `yfinance` birincil + İş Yatırım fallback (gelecek commit'lerde).

## Alternatifler (reddedildi)
- A) Sadece yfinance (TEFAS kapsanmaz).
- B) Sadece Takasbank Excel scraping (kırılgan).
- C) borsa-mcp proxy (transport overhead, backend için gereksiz).

## Gerekçe
pytefas dakikada 6 istek rate-limit yönetimi içinde, type-hint'li, MIT lisans, aktif bakım (haftalık canary). borsa-mcp referans implementation rolünde — kodu açık, gerekince kaynakları (yfinance, KAP, TCMB EVDS) doğrudan import edilir.

## Revize tetikleyicisi
TEFAS API kırılırsa veya yfinance BIST verisi gecikirse İş Yatırım kanalı önceliğe geçer. **ADR-029 (M4, 12 Tem 2026)** R3 ile bu stratejiyi güncelledi: pytefas birincil (kanıtlı), yfinance BIST kırık çıktı.

## Kaynak
MCP `adr_log` [8 Mayıs 2026], güncelleme ADR-029.
