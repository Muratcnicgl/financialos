# FinancialOS — Production Deploy Runbook (MA4, Wave-8)

Sıfırdan bir Linux sunucuda canlıya alma. Blok B'de (Murat sunucu kararı sonrası) adım adım çalıştırılır.
**Sunucu:** Oracle Cloud Free Tier (kalıcı ücretsiz VM) VEYA Hetzner ~€4/ay. Min: 1 vCPU / 1GB RAM / 20GB disk.

## Ön-koşullar (bir kez)
1. **Domain (önerilir):** bir alan adının A kaydını sunucu IP'sine yönlendir (Let's Encrypt için). IP-only da mümkün ama HTTPS zor.
2. **Portlar:** sunucu firewall'unda **80 + 443** açık (SSH 22 zaten). DB portu (5432) **AÇMA** (compose iç ağda).

## Kurulum adımları
```sh
# 1) OS + Docker (Ubuntu/Debian örneği)
sudo apt-get update && sudo apt-get install -y git
curl -fsSL https://get.docker.com | sudo sh          # Docker Engine + compose plugin
sudo usermod -aG docker $USER && newgrp docker        # docker'ı sudo'suz kullan

# 2) Repo
git clone https://github.com/Muratcnicgl/financialos.git && cd financialos

# 3) Production secret'ları (GERÇEK değerler — git'e/chat'e DÜŞMEZ)
cp .env.prod.example .env.prod
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY üret
nano .env.prod   # SECRET_KEY, POSTGRES_PASSWORD, DOMAIN, LLM key(ler) doldur — placeholder BIRAKMA (fail-fast reddeder)

# 4) TLS sertifikası (Let's Encrypt) — chicken-egg bootstrap (bir kez)
export DOMAIN=$(grep '^DOMAIN=' .env.prod | cut -d= -f2)
export EMAIL=seninmail@example.com
sh deploy/init-letsencrypt.sh          # dummy cert → nginx → gerçek cert → reload

# 5) Tüm stack'i ayağa kaldır
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Doğrulama (canlı-gate)
```sh
docker compose -f docker-compose.prod.yml ps          # db/backend/scheduler/web/certbot = Up
curl -fsS https://$DOMAIN/api/health                    # {"status":"ok"}
# Tarayıcı: https://$DOMAIN → login → gerçek işlem gir → cockpit güncellendi (KULLANIM-GATE)
```
- **Scheduler (cron 7/24):** `scheduler` servisi sürekli çalışır → fiyat cron 02:45, batch 03:00 vb. **PC-kapalı sorunu ÇÖZÜLDÜ**
  (Wave-4 M4'ün prod-daemon gerekçesi, ADR-035). 24 saat sonra: `docker compose logs scheduler | grep price` → fiyat yazıldı mı.
- **RLS aktif:** app `financialos` NON-superuser rolüyle bağlanır (ADR-038) → RLS 2. savunma canlı.

## Güncelleme (yeni sürüm)
```sh
sh scripts/deploy.sh     # git pull → build → migrate → up → healthcheck (başarısızsa OTOMATİK ROLLBACK)
```

## Yedekleme
```sh
# Postgres dump (cron ile günlük önerilir)
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U financialos financialos > backup-$(date +%F).sql
```

## Sorun giderme
- **nginx başlamıyor:** TLS cert yok → `deploy/init-letsencrypt.sh` koşuldu mu? Logs: `docker compose logs web`.
- **backend başlamıyor:** `.env.prod` SECRET_KEY placeholder/boş mu? Fail-fast reddeder → gerçek değer koy. Logs: `docker compose logs backend`.
- **fiyat güncellenmiyor:** `docker compose ps scheduler` Up mı? `docker compose logs scheduler`.
- **DB bağlanamıyor:** `db` healthy mi? `docker compose ps db`. POSTGRES_PASSWORD .env.prod ile compose DATABASE_URL eşleşiyor mu.

## Geri alma (manuel)
```sh
git reset --hard <önceki-tag>   # ör. milestone-<N>
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```
