# Wave-4 İskelet (Wave-3 M15'te hazırlandı — KARAR YOK)

> ## ℹ️ 52 GÜN DOKUNULMADI — 5 Eylül 2026'da DENETLENDİ
>
> Wave-4 koşuldu ve kapandı; bu belge bir yol haritası değil, onun girdi kaydıdır.
> Listelediği devir maddelerinden **mobil platform (ADR-032) bugün hâlâ açıktır** ve
> depodaki tek açık STUB odur (ölçüldü) — `goal-charter-wave8-iskelet.md`'nin mobil
> maddesiyle aynı konu. Diğer maddeler ya karara bağlandı ya da kapsam dışına alındı.
> Planlama için aktif hatlar okunur: `masterprompt-koc.md` · `wave-y-ledger.md`.

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

---

## Wave-4 Detay (M32, 14 Tem 2026)

### ✅ BUG #157 KAPANDI (M16) — Security Hardening'den çıkarıldı
SECRET_KEY startup fail-fast Wave-3-Tamamlama M16'da uygulandı (app/settings.py). Bu madde
artık Wave-4 kapsamı DEĞİL. Kalan Security Hardening maddeleri (JWT rotation, HTTPS-enforce
middleware, env-config genişletme) Wave-4'te.

### 1. Mobil Platform (ADR-032 — karar bekliyor)
- **Sorular:** React Native + Expo (native his, ayrı kod) vs PWA (kod %95 paylaşım, App Store yok)?
  iOS Safari PWA kısıtları 2026? Offline-first? Push (vade hatırlatma) hangi yol?
- Backend REST hazır (ikisi de tüketebilir). D1: Expo Router olgunluğu, iOS PWA capability.

### 2. Aile Hesabı Paylaşımı (ADR başlık)
- **İzin modeli:** owner + viewer + editor. Bir kullanıcının hesabını başkasıyla paylaşma.
  Row-level yetki (user_id + shared_with + role). KVKK: paylaşım açık rızası.
- ONERI #017 family_mode (anne emaneti gibi 3. taraf cüzdanlar).

### 3. Kripto (ADR-031 devamı)
- **Numeric(28,8) migration** (satoshi 8 ondalık) — para-kolonları geniş migration (ADR-030 revize-tetiği).
- CoinGecko provider (free tier key'siz). TR kripto vergi/regülasyon araştırması (D1).

### 4. PostgreSQL + RLS Geçişi (Wave-5+, ADR-030/033 depolama sınırı)
- SQLite → PostgreSQL (multi-user ölçek + gerçek DECIMAL + Row-Level Security).
- Migration stratejisi: alembic Postgres-uyumlu, veri taşıma script.

### 5. TR Open Banking / ÖHVPS (H2 2026, ADR başlık)
- BDDK Açık Bankacılık ile otomatik hesap/işlem senkron (elle giriş biter).
- Sorular: ÖHVPS lisans/sandbox, hangi bankalar, KVKK (ADR-033 ile bağlı).

### 6. Observability (Sentry — Wave-5)
- Structured logging M23'te yapıldı (JSON prod). Sentry error tracking + APM Wave-5.

### 7. Frontend Design System (Wave-4)
- shadcn/ui geçişi değerlendirmesi (mevcut Tailwind utility → component sistemi). React Router
  (mevcut router'sız tab-app → gerçek routing, M17/M18 handler'ları basitleşir).

### 8. 🐛 BUG — Google OAuth Consent Screen "External Test" limiti
- **Durum:** Google Cloud consent screen "External / Testing" modunda — **100 kullanıcı sınırı**
  + her girişte "unverified app" uyarısı. Test users listesindeki (muraticgil@gmail.com) çalışır.
- **Wave-4 fix:** consent screen "Publish"/"Production" → Google doğrulama süreci (privacy policy
  URL, domain doğrulama, scope justification). ADR gerekli. Prod OAuth öncesi zorunlu.

### 9. Kalan küçük Wave-4 (Wave-3'ten devreden)
- Frontend a11y (W3-018 modal role/focus-trap, W3-019 dokunma-hedefi), index-key (W3-016),
  router-refactor, raw-formatter consistency (M31). EVDS canlı endpoint doğrulama (M19 R3).
- P2/P3 düşük: tema-duyarlılık (FE-008/UX-020), modal scroll (FE-031), DB CHECK constraint,
  quantize konvansiyonu, pagination, N+1/cache (PERF). Query→select göçü (P2-1), coach.py böl (P2-12).
