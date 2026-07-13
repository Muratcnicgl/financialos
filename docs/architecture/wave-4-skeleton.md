# Wave-4 İskelet (Wave-3 M15'te hazırlandı — KARAR YOK)

**Tarih:** 13 Tem 2026 · **Durum:** İskelet (kararlar Wave-4 başında D1+K10 ile) · **Kaynak:** Wave-3 ertelenenler + charter.

> **İLKE (M7/M15):** Bu belge Wave-4'ü materyalize eder, KARAR VERMEZ.

## Wave-3'ten Devreden (ertelenen)

### 1. Mobil Platform (ADR-032 — Wave-3 SCOPE DIŞIydı)
- PWA vs RN+Expo. iOS Safari PWA kısıtları, offline-first, push (vade hatırlatma). Backend REST hazır.

### 2. Aile Hesabı Paylaşımı
- Multi-user "farklı bireyler ayrı hesap" M11'de yapıldı; **aile/paylaşımlı cüzdan** (anne emaneti gibi 3. taraf) ertelendi. ONERI #017 family_mode.

### 3. Kripto (ADR-031 kapsam dışı)
- `Numeric(28,8)` migration (satoshi 8 ondalık) — para-kolonları geniş migration. CoinGecko provider. TR vergi/regülasyon.

### 4. PostgreSQL + RLS (ADR-030/033 depolama sınırı)
- Multi-user ölçeklenince SQLite→PostgreSQL (gerçek DECIMAL + row-level security). Decimal depolama tamamlama.

### 5. Kalan Backlog (Wave-3 M14'ten)
- W3-007/010-014/018-022/025/031/032/035-038/043-046/047(query göçü)/048(coach.py böl)/053/055/057/061/062/063/064-068 (a11y, locale, kod-borcu, feature ONERI'ler). ONERI #029 (AST scanner).

### 6. Koç Gelişmiş (ADR-034 devamı)
- Ücretli sağlayıcı (Anthropic Claude birincil). Sub-agent routing (intent classifier). Prompt caching (P2-13). Cloudflare/HF/Mistral entegrasyon.

### 7. Frontend Multi-asset UI (M12'den)
- Accounts panelinde asset-type seçici (stock/gold/fx). Backend dispatch hazır.

### 8. TR Open Banking / ÖHVPS (H2 2026)
- BDDK Açık Bankacılık ile otomatik hesap/işlem senkron. Elle giriş biter. KVKK (ADR-033 ile bağlı).

### 9. Vector+Graph Hibrit Memory (Mem0g — MCP Wave-3 Backlog item)
- SQLite tek-tablo → vector store (semantic) + graph store (entity relations). Multi-hop reasoning.

## Sonraki Adım
Wave-4 başında: her özellik için D1 (2-3 sektör referans) → Research Log → karar. ADR-032 (mobil) + yeni ADR'ler. Bu belge iskelet.
