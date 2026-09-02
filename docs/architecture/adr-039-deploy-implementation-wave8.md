# ADR-039 — Deploy implementasyonu (Docker + Compose + nginx/HTTPS) — Wave-8 Blok A

**Tarih:** 18 Temmuz 2026 · **Durum:** Kabul edildi, altyapı STATİK-DOĞRULANDI, canlı-deploy Murat sunucu-kapısı bekliyor
(Wave-8 MA1-MA4) · **İlgili:** ADR-035 (deploy stratejisi — bu ADR onu somutlaştırır), ADR-038 (Postgres hibrit + RLS),
ADR-013 (Alembic tek şema kaynağı), BUG #157 (SECRET_KEY fail-fast)

## Bağlam
ADR-035 (Wave-3) production deploy **stratejisini** (Docker-first + reverse proxy + cron-daemon) karara bağlamıştı ama
kodda somut imaj/compose/nginx **yoktu**. Wave-8 ÜRÜN-DNA'sı (Murat, 18 Tem): "DEPLOY + PWA, PARA EN SONA — altyapı
parasız/hedef-agnostik, sunucu adımı insan-kapısı". Kısıt: **docker CLI bu dev ortamında yok** → tüm GATE'ler statik
doğrulama (YAML parse, `sh -n`, config-yapı), canlı-deploy Murat'ın Oracle Free Tier VM'inde koşulacak.

## Karar

### 1. Multi-stage prod imajı (`Dockerfile`)
- **builder** (pip wheel) → **runtime** (python-slim + `libpq5` psycopg2 için). Non-root **`appuser` (uid 10001)**,
  `USER appuser`. HEALTHCHECK `curl /api/health`. Secret imaja GİRMEZ (`.dockerignore` `.env*` hariç tutar).
- Web sunucu: **gunicorn + `uvicorn.workers.UvicornWorker`** (FastAPI resmi prod deseni), `WEB_CONCURRENCY` worker sayısı.

### 2. `docker-entrypoint.sh` — SERVICE_MODE ile web/scheduler ayrımı
- `web`: `alembic upgrade head` (şema, ADR-013) + gunicorn; **`SCHEDULER_ENABLED=false`**.
- `scheduler`: tek-worker uvicorn + `SCHEDULER_ENABLED=true` (APScheduler daemon).
- **Gerekçe:** çok-worker'lı web'de her worker cron'u ayrı tetiklerse fiyat çekimi/batch **N kez** çalışır. Scheduler'ı
  AYRI tek servise almak çift-tetiklemeyi kod-seviyesinde imkânsız kılar. `app/main.py` lifespan'a `SCHEDULER_ENABLED`
  gate eklendi (dev default açık — geriye uyumlu).

### 3. `docker-compose.prod.yml` — 5 servis
- **db** (postgres:16-alpine): dışa **port AÇILMAZ** (`expose`, `ports` değil) → DB internete kapalı, yalnız iç ağ.
  healthcheck `pg_isready`.
- **backend** (gunicorn web): `DATABASE_URL=postgresql://financialos:${POSTGRES_PASSWORD}@db:5432/financialos` —
  **NON-superuser `financialos` rolü** (ADR-038 RLS için: superuser RLS'i bypass eder). Zorunlu secret `${SECRET_KEY:?}`
  (eksikse compose başlamaz).
- **scheduler** (SERVICE_MODE=scheduler): 7/24 cron daemon → **PC-kapalı sorunu çözülür** (ADR-035 prod-daemon gerekçesi).
- **web** (nginx): 80+443, SPA + `/api` proxy.
- **certbot**: 12 saatte bir `certbot renew` (Let's Encrypt 90 gün).

### 4. nginx + HTTPS (`deploy/nginx.conf.template`, envsubst `${DOMAIN}`)
- HTTP :80 → ACME challenge webroot + **301 HTTPS redirect**. HTTPS :443 → SPA `try_files` + `/api` proxy `backend:8000`.
- **A-rating TLS:** TLSv1.2+1.3, güçlü ECDHE cipher. **Güvenlik başlıkları:** HSTS (1 yıl includeSubDomains), CSP
  (`default-src 'self'; frame-ancestors 'none'`), X-Frame DENY, X-Content-Type nosniff, `server_tokens off` (W3-042/SEC-005).
- **`deploy/init-letsencrypt.sh`:** chicken-egg çözer (dummy openssl cert → nginx :443 up → gerçek cert → reload). Canlıda BİR KEZ.

### 5. Secret yönetimi + fail-fast (`.env.prod.example` + `app/settings.py`)
- `.env.prod.example` PLACEHOLDER şablon (git'te); gerçek `.env.prod` `.gitignore`'da (`!.env.prod.example` allowlist).
- `secret_key_problems()`: boş / `dev-default` / **`REPLACE` placeholder** / <32 char reddeder. `ENVIRONMENT=production` +
  sorunlu SECRET_KEY → startup RuntimeError (**uygulama açılmaz**, BUG #157). Placeholder-reddi kritik: şablon git'te açık,
  operatör değiştirmezse bilinen-secret'la deploy olurdu.

### 6. Deploy otomasyonu (`scripts/deploy.sh` + `docs/deployment/runbook.md`)
- `deploy.sh`: git pull → build → up (entrypoint migrate) → healthcheck (60s) → **başarısızlıkta OTOMATİK ROLLBACK** (trap:
  önceki commit'e reset + rebuild).
- `runbook.md`: sıfırdan sunucu (OS+Docker → repo → .env.prod secret → init-letsencrypt → compose up → KULLANIM-GATE →
  güncelleme/yedek/sorun-giderme).

## D1 — Sektör referansları
FastAPI resmi deploy (gunicorn+UvicornWorker) · multi-stage Python (wheel builder→slim, imaj küçültme) · non-root container
(OWASP Docker Top-10) · Let's Encrypt certbot-webroot (nginx resmi deseni) · HSTS/CSP (Mozilla Observatory A-rating) ·
12-factor config (env'den secret) · DB dışa-kapalı (compose iç ağ, saldırı yüzeyi).

## Sonuç
Deploy altyapısı **parasız + statik-doğrulandı** (docker CLI dev'de yok → YAML/`sh -n`/config-yapı gate'leri geçti).
**Canlı-deploy + KULLANIM-GATE Murat'ın Oracle VM'ini bekliyor** (KURAL-3 gerçek elle-görev: hesap/ödeme/uzak-VM — otomasyon yapamaz). Bu ADR canlı-deploy doğrulanınca "sahada çalıştı" notuyla güncellenecek.
