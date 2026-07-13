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

## Security Hardening (Wave-4 kritik milestone)

Kaynak: `docs/kalite-seruveni/env-denetim-rapor-14tem.md` (14 Tem 2026 env denetimi).

- **BUG #157 — SECRET_KEY startup validation (fail-fast).** R3: dev-default fallback YOK
  (auth.py:_secret() boşsa RuntimeError raise — fail-closed); ama doğrulama **lazy** (ilk auth
  çağrısında, boot'ta değil). Fix: `ENVIRONMENT=production` ise startup'ta SECRET_KEY var+entropy
  (≥32) zorunlu → uygulama açılmaz; development'ta warning. (settings.py yok — env-config katmanı
  bu milestone'da eklenebilir.)
- **Environment-based config validation** (production vs development ayrımı — `ENVIRONMENT` env).
- **Startup security check:** SECRET_KEY entropy · SMTP_PASS format · DATABASE_URL prod-safe
  (SQLite→PostgreSQL uyarısı) · CORS non-wildcard doğrulaması.
- **JWT rotation stratejisi:** SECRET_KEY değişince graceful token invalidation (mevcut RevokedToken
  + `kid` header veya çift-secret geçiş penceresi).
- **Rate limiting production değerleri** (Wave-3 dev değerleri: AUTH_RATE_MAX=10/60s → prod ayarı).
- **CORS whitelist** production (Wave-3'te env-driven yapıldı, W3-040; prod domain zorunlu kıl).
- **HTTPS enforce middleware** (reverse-proxy dışında app-katmanı redirect, ADR-035 Caddy tamamlayıcı).
- **SMTP gönderen doğrulama** (env raporu: raw gmail SMTP_FROM → Brevo verified-sender/SPF/DKIM gerekli).

### 10. OAuth Frontend UI (M11 backend hazır)
- Login.jsx'e "Google ile giriş" + "GitHub ile giriş" butonları (→ `/api/auth/oauth/{provider}/login`).
- `/auth/oauth-success` sayfası: URL'den access_token+refresh_token okur, `setTokens()`, uygulamaya yönlendirir.
- `/auth/reset` sayfası (M11 SMTP şifre sıfırlama linkini tüketen — backend hazır, UI eksik).
- Not: token'lar şu an URL query'de (MVP); Wave-4'te httpOnly cookie güvenlik iyileştirmesi.
