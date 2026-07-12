# ADR-035 — Production Deployment Strategy

**Tarih:** 13 Tem 2026 · **Durum:** 🟡 TASLAK — karar Wave-3 M10'da (D1 + K10 sonrası) · **İlgili:** M4 fiyat otomasyonu (cron), open-source self-host

## Bağlam
M4 pytefas cron **kodu doğru**, elle-tetiklendiğinde PriceHistory yazıyor (kanıt: TLY 7277.90 [TEFAS] 12 Tem 14:07). **AMA** uvicorn dev sunucu daemon değil → gece 02:45 otomatik çekim **sahada doğrulanmadı**. Ayrıca open-source AGPL topluluk için `git clone` sonrası kurulum rehberi eksik. Wave-3'te production deployment + self-host paketleme kararı gerekli.

## Açık Sorular (KARAR BEKLİYOR — Wave-3 M10)
1. **Süreç yöneticisi:** systemd service (Linux VPS'de tek başına) vs Docker container vs docker-compose — self-host topluluk için en düşük friksiyon hangisi?
2. **Reverse proxy:** Caddy vs nginx? Otomatik HTTPS (Let's Encrypt) önemli mi?
3. **Backup stratejisi:** SQLite dosyası günlük snapshot script, kaç gün retention?
4. **Monitoring:** log dosyası yeter mi, yoksa Prometheus/Grafana ekle mi?
5. **Persistent storage:** SQLite volume mount, log rotation (logrotate/Docker).
6. **.env production değişkenleri:** SECRET_KEY generation, DATABASE_URL prod path, TCMB EVDS API key vb.
7. **Fresh clone kurulum rehberi:** `docs/deployment/README.md` formatı (git clone → kurulum → başlatma).

## D1 (Wave-3 M10'da yapılacak) → Research Log
Sektör referansları (5+): Firefly III deployment docs, Beancount fava self-host, Maybe Finance production Rails, Grafana Loki self-host, Umami self-host, Sentry self-host — bunların nasıl paketlendiğini oku (Docker vs bare, proxy, backup, env).

## Karar
**(BOŞ — Wave-3 M10'da D1 + K10 üç boyut muhakemesi ile: en kaliteli + TR self-host topluluk için en düşük friksiyon yol.)**

## Kaynak
Wave-2 M4 (cron sahada-doğrulanmadı nüansı), wave-3-master-plan.md, goal-charter-wave3.md M10.
