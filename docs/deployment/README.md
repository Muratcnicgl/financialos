# FinancialOS — Self-Host / Production Deployment

Bu rehber FinancialOS'u kendi sunucunda (VPS, ev sunucusu) çalıştırmak içindir.
İki yol: **Docker (önerilen, tek komut)** ve **bare-metal systemd (Docker'sız)**.

Karar gerekçesi: [ADR-035](../architecture/adr-035-production-deployment.md).

---

## Mimari

```
İnternet ──HTTPS──▶ Caddy (web)  ──/api/*──▶ uvicorn (backend, :8000)
                       │                          │
                    SPA statik                 SQLite (/data volume)
                    (frontend/dist)            + APScheduler cron (fiyat çekimi 02:45)
```

- **backend**: FastAPI + uvicorn (`--reload` YOK → APScheduler cron tek-process'te düzgün
  çalışır; M4'te dev sunucuda çalışmayan gece fiyat çekiminin kök çözümü). SQLite dosyası
  kalıcı volume'de. Başlangıçta `alembic upgrade head`.
- **web (Caddy)**: derlenmiş SPA'yı sunar, `/api/*`'yi backend'e proxy'ler, gerçek domain
  verilirse **otomatik Let's Encrypt HTTPS** + güvenlik başlıkları (HSTS/X-Frame/nosniff).
  Aynı origin olduğu için CORS gerekmez.

---

## Yol 1 — Docker (önerilen)

Gereksinim: Docker + Docker Compose (v2).

```bash
git clone <repo-url> financialos && cd financialos
cp .env.example .env
```

`.env` düzenle (en az):
```ini
DOMAIN=financialos.example.com     # gerçek domain → otomatik HTTPS; test için localhost
LLM_PROVIDER=fallback
GEMINI_API_KEY=...                 # en az bir LLM sağlayıcı
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
CORS_ORIGINS=https://financialos.example.com
```

Başlat:
```bash
docker compose up -d --build
docker compose logs -f backend      # 'uvicorn başlıyor' + 'alembic upgrade' gör
```

- `http://localhost` (veya domain'in) → uygulama.
- İlk kurulumda veri yok: `docker compose exec backend python -m scripts.setup_data`
  (Murat'ın demo verisi) **VEYA** boş başla, UI'dan gir.
- Sağlık: `curl http://localhost/api/health`.

Güncelleme:
```bash
git pull && docker compose up -d --build   # alembic upgrade otomatik çalışır
```

---

## Yol 2 — Bare-metal (systemd, Docker'sız)

Linux VPS'te, Docker istemeyenler için.

```bash
sudo useradd -r -m -d /opt/financialos financialos
sudo -u financialos git clone <repo-url> /opt/financialos
cd /opt/financialos
sudo -u financialos python3.11 -m venv venv
sudo -u financialos ./venv/bin/pip install -r requirements.txt
sudo -u financialos cp .env.example .env    # düzenle (yukarıdaki gibi)

# Frontend'i derle (bir kez) — Caddy/nginx bunu sunar
cd frontend && npm ci && npm run build && cd ..

# Servis
sudo cp deploy/financialos.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now financialos
sudo systemctl status financialos            # aktif mi
journalctl -u financialos -f                 # loglar

# Reverse proxy: Caddy kur, Caddyfile'ı düzenle (root'u frontend/dist'e, proxy'yi :8000'e)
# veya nginx: /api → 127.0.0.1:8000, / → frontend/dist (try_files SPA fallback).
```

---

## Yedekleme

SQLite tek dosya — online backup (bağlantı kesmez):

```bash
# Docker:
docker compose exec backend python -m scripts.backup --keep-days 30
# Bare-metal (systemd timer otomatik 03:00):
sudo cp deploy/financialos-backup.{service,timer} /etc/systemd/system/
sudo systemctl enable --now financialos-backup.timer
```

Yedekler `data/backups/YYYY-MM-DD-HHMM.db`, 30 günden eskisi otomatik silinir.

---

## İzleme / Sağlık

- **Healthcheck**: `GET /api/health` → `{"status":"ok",...}`. Docker `HEALTHCHECK` ile
  container sağlığı otomatik. Uptime izleme (UptimeRobot vb.) bu endpoint'e bağlanabilir.
- **Loglar**: Docker `docker compose logs`, systemd `journalctl -u financialos`.
  Structured logging + error tracking (Sentry) Wave-3 M14 backlog'unda (OBS-001/012).
- **Cron doğrulama**: fiyat çekimi her gece 02:45. Test için `OLLAMA`/scheduler interval'ını
  geçici düşürüp `PriceHistory` satır artışını izle (ADR-035 doğrulama notu).

---

## Fiyat Otomasyonu (cron) — Production Notu

M4'te fiyat çekimi kodu doğru ama dev `uvicorn --reload` daemon olmadığı için gece
çalışmıyordu. Production'da (`docker compose` veya systemd) uvicorn **reload'suz tek
process** olarak sürekli ayakta → APScheduler job'ı (02:45) düzgün tetiklenir. Bu, M4'ün
"sahada doğrulanmadı" nüansının çözümüdür (ADR-035).

---

## .env Değişkenleri (production)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `DOMAIN` | evet (HTTPS için) | Caddy domain'i; localhost dışında → otomatik Let's Encrypt |
| `LLM_PROVIDER` | evet | `fallback` \| `gemini` \| … |
| `GEMINI_API_KEY` (vb.) | en az 1 | Koç için LLM sağlayıcı |
| `SECRET_KEY` | **EVET** | Oturum/JWT. **Boşsa uygulama AÇILMAZ** (M80: compose `ENVIRONMENT=production` → fail-fast, BUG #157). `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | opsiyonel | Prod domain (aynı-origin'de gereksiz) |
| `DATABASE_URL` | opsiyonel | Docker'da `/data` volume'e sabit |
| `ENVIRONMENT` | opsiyonel | Compose default `production` (SECRET_KEY fail-fast + /docs kapalı). Dev için `.env`'de `development` yaz. |
| `AUTH_ENABLED` | opsiyonel | Compose default `true` (JWT zorunlu). Tek-kullanıcı fallback için `.env`'de `false`. |

> **M80 doğrulama notu (18 Tem 2026):** `docker-compose.yml` + `Dockerfile` + `Dockerfile.web` + `Caddyfile` +
> `docker-entrypoint.sh` **statik olarak doğrulandı** (YAML geçerli, `/api/health` healthcheck hedefi mevcut,
> uvicorn/alembic bağımlılıkları var, vite `outDir=dist` ↔ Caddy COPY tutarlı, reverse-proxy + güvenlik başlıkları
> doğru). **Canlı `docker compose up` bu Windows dev ortamında KOŞTURULAMADI** (docker CLI yok — ADR-035'in
> "prod'da daemon" gerekçesi + rapor §B23 KANIT YOK maddesi). Compose artık prod-güvenli default'larla gelir:
> `ENVIRONMENT=production` + `AUTH_ENABLED=true` → zayıf/boş SECRET_KEY ile açılmaz (fail-fast R3 ile doğrulandı).
