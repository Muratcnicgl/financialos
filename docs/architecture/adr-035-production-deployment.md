# ADR-035 — Production Deployment Strategy

**Tarih:** 13 Tem 2026 · **Durum:** ✅ KARAR VERİLDİ (Wave-3 M10, D1 + K10) · **İlgili:** M4 fiyat otomasyonu (cron), open-source self-host, W3-042 (security headers)

## Bağlam
M4 pytefas cron **kodu doğru**, elle-tetiklendiğinde PriceHistory yazıyor (kanıt: TLY 7277.90 [TEFAS] 12 Tem 14:07). **AMA** uvicorn dev sunucu (`--reload`) daemon değil → gece 02:45 otomatik çekim **sahada doğrulanmadı**. Ayrıca open-source topluluk için `git clone` sonrası kurulum rehberi eksik. Wave-3'te production deployment + self-host paketleme kararı gerekli.

## D1 — Sektör Referansları (5+, Research Log'a da işlendi)

| Proje | Paketleme | Reverse proxy | Backup | Not |
|-------|-----------|---------------|--------|-----|
| **Firefly III** (PHP/Laravel) | Docker-first + docker-compose (bare-metal de belgeli) | nginx/Apache; harici HTTPS | DB dump script | Self-host referans standardı; compose ile tek-komut |
| **Beancount fava** (Python) | Bare (`pip install`, `fava ledger`) + reverse proxy | nginx/Caddy + basic auth | dosya-tabanlı (ledger metin) | Küçük footprint, systemd + proxy tipik |
| **Maybe Finance** (Rails) | Docker + docker-compose (Postgres) | içinde/harici | Postgres dump | Modern fintech; compose primary |
| **Umami** (Node analytics) | Docker + docker-compose | harici (Caddy/nginx) | DB dump | Tek-komut compose, minimal env |
| **Grafana Loki / Sentry** | Docker (compose, çok-servis) | dahili | volume snapshot | Ağır; bizim ölçek için fazla |
| **Caddy** (reverse proxy) | — | **otomatik Let's Encrypt HTTPS** | — | nginx'e göre sıfır-config TLS |

**Çıkarım:** Self-host topluluğun beklentisi **Docker Compose ile tek-komut**. FastAPI+SQLite+SPA için en düşük friksiyon: backend container (uvicorn daemon) + Caddy (SPA statik + `/api` proxy + otomatik HTTPS). SQLite tek-dosya olduğu için backup = dosya snapshot (Postgres dump karmaşasına gerek yok). nginx yerine **Caddy**: otomatik TLS, daha az config (Firefly nginx kullanıyor ama manuel certbot gerekiyor — solo dev için Caddy daha iyi).

## K10 — Üç Boyut Muhakemesi

- **MUHAKEME (sektör + mantık):** Docker Compose sektörde self-host'un fiili standardı (Firefly/Maybe/Umami). SQLite → dosya-backup yeterli, DB-server gerekmez. Caddy otomatik HTTPS = nginx+certbot'tan daha az friksiyon. Cron sorunu bir kod bug'ı değil, `--reload` dev-sunucu artefaktı: prod'da reload'suz tek-process uvicorn APScheduler'ı düzgün çalıştırır (in-process scheduler, lifespan'da `start_scheduler`).
- **BENİ DÜŞÜN (Murat: solo öğrenci, Windows dev, Linux VPS hedef):** Docker cross-platform (Windows'ta geliştir, Linux'ta aynı image). Ama Docker öğrenme/kaynak maliyeti var → **bare-metal systemd alternatifi** de sunulmalı (öğrenci-bütçe VPS, Docker'sız). İki yol = esneklik.
- **GENELİ DÜŞÜN (topluluk + TR + KVKK):** Self-host = veri kullanıcının sunucusunda kalır (SQLite dosyası) → **KVKK-dostu** (veri yurt-içi/kendi kontrolünde). Topluluk tek-komut compose bekler ama bare-metal isteyeni de kapsa. Güvenlik başlıkları (HSTS/CSP/X-Frame, W3-042) reverse-proxy katmanında (Caddy) — app'i kirletmez.

## Karar

1. **Süreç yöneticisi:** **Docker Compose (birincil)** — `backend` (uvicorn daemon, reload YOK) + `web` (Caddy). **systemd (alternatif)** bare-metal için (`deploy/financialos.service`).
2. **Reverse proxy:** **Caddy** — otomatik Let's Encrypt HTTPS + SPA statik sunumu + `/api` proxy + güvenlik başlıkları. (nginx eşdeğeri README'de tarif, tercih Caddy.)
3. **Backup:** `scripts/backup.py` (mevcut) — SQLite online snapshot, **30 gün retention**. Docker: `compose exec`; bare-metal: systemd timer (03:00).
4. **Monitoring:** `/api/health` endpoint (mevcut) + Docker `HEALTHCHECK` + log (journald/`compose logs`). Structured logging + Sentry → M14 backlog (OBS-001/012).
5. **Persistent storage:** SQLite `/data` named volume (Docker) veya `./data` (bare). Log rotation: journald (systemd) / Docker log driver.
6. **.env production:** `DOMAIN` (Caddy HTTPS), `SECRET_KEY` (M11 auth, şimdiden üretilir), `CORS_ORIGINS` (W3-040), `DATABASE_URL` (`/data` volume), LLM key'leri.
7. **Fresh-clone rehberi:** `docs/deployment/README.md` — iki yol, tek-komut.

**M4 cron çözümü:** Production `docker compose up` / systemd → uvicorn `--reload`'suz **tek-process daemon** → APScheduler cron (02:45) sürekli ayakta ve tetiklenir. "Sahada doğrulanmadı" nüansı deployment-config ile kapanır (kod değişikliği gerekmez).

## Uygulama (M10)
`Dockerfile` (backend, alembic+uvicorn entrypoint) · `Dockerfile.web` (node build → Caddy) · `Caddyfile` (SPA+proxy+HSTS) · `docker-compose.yml` · `.dockerignore` · `deploy/financialos.service` + `financialos-backup.{service,timer}` · `.env.example` prod bloğu · `docs/deployment/README.md`.

## Kaynak
Wave-2 M4 (cron sahada-doğrulanmadı nüansı), wave-3-master-plan.md, goal-charter-wave3.md M10, D1 (Firefly III / Beancount fava / Maybe Finance / Umami / Caddy).
