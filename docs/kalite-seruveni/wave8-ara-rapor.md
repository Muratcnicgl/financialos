# WAVE-8 ARA RAPORU — DEPLOY + PWA (⚠️ KAPANIŞ DEĞİL — canlı-deploy bekliyor)

**Durum:** 🟡 **DEVAM — "GOAL TAMAM WAVE-8" DENMEDİ.** Statik/parasız her şey bitti; canlı-deploy (Blok B) Murat'ın Oracle
Free Tier VM'ini bekliyor (KURAL-3 insan-kapısı). Bu rapor Blok D'nin **statik "rapor" kalemidir**; final kapanış-raporu +
GOAL TAMAM kaydı ancak canlı-deploy doğrulanınca yazılacak (`milestone-101-wave8-kapanis`).
**Tarih:** 18 Tem 2026 · **Rollback:** `pre-wave-8` (79e0b8c) · **Charter:** `goal-charter-wave8.md`

## Yapılan (statik-doğrulandı, docker/sunucu-bağımsız)

### Blok A — Deploy altyapısı (PARASIZ) ✅
| MS | Tag | Çıktı |
|----|-----|-------|
| MA1 | `milestone-93-prod-docker-imaj` | Multi-stage `Dockerfile` (non-root appuser uid 10001, libpq5, gunicorn+UvicornWorker) · `docker-entrypoint.sh` SERVICE_MODE web/scheduler · `docker-compose.prod.yml` 5 servis (db dışa-kapalı, backend RLS non-superuser, ayrı scheduler daemon, nginx) |
| MA2 | `milestone-94-nginx-https` | `deploy/nginx.conf.template` (HTTP→HTTPS 301 + ACME webroot + HTTPS SPA/proxy) · A-rating TLS (TLSv1.2+1.3, HSTS 1yr, CSP, X-Frame DENY, server_tokens off) · certbot servisi · `init-letsencrypt.sh` chicken-egg |
| MA3 | `milestone-95-prod-env-secret` | `.env.prod.example` placeholder + `.gitignore` allowlist · `secret_key_problems()` REPLACE-placeholder reddi · ENVIRONMENT=production + sorunlu SECRET_KEY → startup RuntimeError (BUG#157) |
| MA4 | `milestone-96-deploy-runbook` | `scripts/deploy.sh` (git pull→build→migrate→healthcheck, başarısızlıkta OTOMATİK ROLLBACK) · `docs/deployment/runbook.md` sıfırdan-sunucu |

### Blok C — PWA + mobil (HTTPS üzerine) ✅ (kod; canlı-gate bekliyor)
| MS | Tag | Çıktı |
|----|-----|-------|
| MC1 | `milestone-99-pwa-temel` | vite-plugin-pwa: `manifest.webmanifest` (standalone, 4 ikon + maskable) + workbox SW (app-shell precache + `/api` NetworkFirst) + iOS `apple-*` meta. Build: sw.js/manifest/registerSW üretiliyor |
| MC2 | `milestone-100-mobil-uyum` | 390px Explore denetimi → P0 IncomeDebt sekme kırpılması + MetricCard truncate; P1 7 ham `<button>` 44px'e (ADR-011), DebtStrategy grid, WorkspaceSwitcher |

### Blok D — statik-prep ✅
- **ADR-039** (deploy impl) + **ADR-040** (PWA/mobil=PWA native-değil) + `adr-index` güncel.
- **PROJE.md** aktif-goal → 🟡 Wave-8 DEVAM (Wave-7 arşive).
- **`goal-charter-wave9-iskelet.md`** (post-deploy gerçek-kullanım UX önceliklendirme).

## Doğrulama (statik gate'ler)
- Backend: **1247 passed / 5 skipped** (4 postgres-yok pg_gate kasıtlı — lokal pg süreci Wave-7 sonunda kapatıldı — + 1 orijinal).
- Frontend: **63 vitest** · `npm run build` OK (SW/manifest üretiliyor).
- Deploy altyapısı: docker CLI dev'de YOK → YAML parse / `sh -n` / config-yapı gate'leri (canlı-deploy Blok B'de).

## KALAN (⏸️ hepsi Murat'ın Oracle VM'ine bağlı — KURAL-3 elle-görev)
1. **Blok B (MB1-MB2):** VM kur → `runbook.md` koş (secret'lar yalnız sunucu `.env.prod`'da, chat'e/git'e DÜŞMEZ) →
   canlı HTTPS + **KULLANIM-GATE** (login→gerçek işlem→cockpit) + **24s sonra fiyat cron canlı yazdı mı**.
2. **MC1/MC2 canlı-gate'leri:** Lighthouse PWA skoru · "ana ekrana ekle" · offline app-shell · gerçek mobil viewport uçtan uca.
3. **Blok D final:** bu raporu canlı-doğrulama bölümüyle tamamla · **GOAL TAMAM WAVE-8** · `milestone-101-wave8-kapanis` tag ·
   MCP GOAL TAMAM W8 · W1 rotasyonu (Working State observation ~85+ şişti).

## Güvenlik notu (deploy = internete açılma)
Production-güvenlik gözüyle kapatıldı: secret imaja/git'e/chat'e girmez (fail-fast + .gitignore) · DB portu dışa kapalı ·
`ENVIRONMENT=production` (/docs kapalı, SEC-015) · AUTH_ENABLED=true · HTTPS zorunlu (HTTP→301) · HSTS/CSP · non-root container ·
RLS non-superuser rolüyle canlı (ADR-038). CORS aynı-origin (nginx). Rate-limit + JSON log mevcut (Wave-3/M35).

---
⚠️ **Bu rapor kapanış DEĞİL.** "GOAL TAMAM WAVE-8" yalnızca yukarıdaki KALAN kalemler canlı-doğrulandıktan sonra yazılır.
Otonom sunucu kiralama / para harcama YAPILMADI (charter + KURAL-3). Sıradaki tetikleyici: Murat Oracle VM'i açar.
