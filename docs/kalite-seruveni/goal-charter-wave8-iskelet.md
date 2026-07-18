# Goal Charter — WAVE-8 İSKELETİ (DEPLOY + MOBİL) — Murat kararı bekliyor

**Durum:** 🔲 TASLAK — Wave-7 kapanışında (Blok E) oluşturuldu. **Henüz aktif goal DEĞİL.**
**Tarih:** 2026-07-18 · **Öncül:** Wave-7 PostgreSQL geçişi (M49-M92) TAMAM.
**Giriş durumu:** 1251 test · coverage %92 · hibrit DB (SQLite dev / Postgres prod) · RLS · BIST+fon otomasyonu canlı.

> Wave-7 veri katmanını prod-hazır yaptı (Postgres/RLS/dual-dialect). Wave-8 = **canlı dünyaya çıkış**: gerçek bir
> sunucuda çalışan + telefondan erişilebilir sistem. İKİSİ DE PARA/HESAP gerektiriyor → Murat kararı olmadan başlamaz.

## 🎯 MURAT'A KARAR SORULARI (Wave-8 ön-koşulları)
1. **VPS var mı / bütçe?** Deploy için bir Linux sunucu (öğrenci-bütçe ~5$/ay yeterli: Hetzner/DigitalOcean).
2. **Domain?** Caddy otomatik HTTPS için bir alan adı (Let's Encrypt). Yoksa IP + self-signed (yarım).
3. **Apple Developer ($99/yıl)?** Native iOS için gerekli. Yoksa PWA (ücretsiz, App Store yok).
4. **Hangi mobil yol?** (aşağıdaki D1 ön-analiz karar için hazır.)

## BLOK A — DEPLOY (canlı Postgres + Caddy TLS)
Gerekçe: M80 Docker Compose statik-doğruladı, M49 postgres profili ekledi — ama HİÇ canlı koşulmadı (docker CLI dev'de yok).
- Gerçek VPS'e `docker compose --profile postgres up` → app `financialos` NON-superuser rolüyle (RLS aktif olsun, M51).
- Caddy otomatik Let's Encrypt HTTPS + güvenlik başlıkları (W3-042). Backup daemon (systemd timer).
- CI'ya postgres service (dual-dialect gate'ler CI'da da koşsun — Wave-7 pg_gate şu an lokal-skip).
- **GATE:** canlı domain → HTTPS → gerçek login → cockpit; RLS canlı (non-superuser); backup alınıyor.

## BLOK B — MOBİL (PWA vs RN+Expo) — D1 ÖN-ANALİZ HAZIR
**PWA** (ADR-009 birinci aşama): ücretsiz, App Store yok, mevcut React'i PWA'ya çevir (vite-plugin-pwa + manifest +
service worker + offline cache). MOB backlog'da 12 madde altyapı. Hızlı kazanım, "add to home screen".
**RN+Expo** (ADR-009/032 ikinci aşama, 032 TASLAK): native deneyim + push + App Store, ama Apple $99 + ayrı kod tabanı +
4-6 ay. Backend FastAPI korunur (API zaten var).
**D1 ön-öneri:** ADR-009 zaten "PWA önce, RN sonra" diyor. Deploy (HTTPS) OLMADAN PWA yarım kalır (service worker HTTPS
ister) → **Blok A (deploy) Blok B'nin (mobil) ön-koşulu.** Murat "sadece masaüstü yeterli" derse Blok B atlanır.

## KAPSAM DIŞI (Wave-8'de de, Murat açık karar vermeden)
Kripto (ADR-031 Wave-4 ertelenmiş, Murat varlık sahibi değil). PostgreSQL ölçek/sharding (tek-kullanıcı için gereksiz).

## Wave-7'den devralınan iç-kalite girdileri (deploy-bağımsız, istenirse)
- 273→ backlog: saf-UX/kozmetik borç (modal a11y, aria-label, 44px, tema tutarlılığı — M85 en ham boyut UX).
- Mimari refactor: coach.py 2641 satır god-module bölme, service/repo katmanı, config merkezileştirme (BE-001/003/004).
- DevOps hattı: ruff/mypy/gitleaks/pip-audit/cov-fail-under CI kapıları.
- Observability: OTel/Prometheus/Sentry (OBS boyutu M85'te büyük oranda açık).

## Wave-8 başlarken (M-ilk)
1. Murat'ın 4 karar sorusuna cevabıyla bu iskeleti tam charter'a çevir (deploy-var-mı → Blok A; mobil-yol → Blok B).
2. `git tag pre-wave-8`. 3. Milestone-log Wave-8 bölümü.
