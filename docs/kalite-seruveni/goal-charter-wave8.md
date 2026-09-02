# Goal Charter — WAVE-8: DEPLOY + PWA (MEGA-CHARTER)

**Tarih:** 2026-07-18 · **Rollback tag:** `pre-wave-8` (79e0b8c)
**Baseline:** `goal-charter-wave8-iskelet.md` + `tam-proje-durum-raporu.md`
**Giriş durumu:** Wave-7 kapanışı · 1251 test · coverage %92 · hibrit DB (SQLite dev / Postgres prod, pgserver-kanıtlı) · auth ON.

---

## ÜRÜN-DNA (Murat, 18 Tem 2026) — TARTIŞMA YOK
- Wave-8 = **DEPLOY + PWA.** Otonom sona kadar sür.
- **PARA EN SONA:** Blok A (deploy altyapısı) hedef-agnostik, **PARASIZ.** Sunucu için ÖNCE Oracle Cloud Free Tier
  (kalıcı ücretsiz VM), OLMAZSA Hetzner ~€4/ay. Parayı Murat verecek — **sunucu adımına gelince DUR ve Murat'a sor**
  (bu tek insan-kapısı).
- **MOBİL = PWA.** Native/App Store/Apple hesabı **KAPSAM DIŞI.** Kişisel 1-2 kullanıcılık app için App Store faydası
  (halka dağıtım) sıfır. Capacitor kapısı ileride için açık bırakılır ama BU WAVE'de kullanılmaz.
- **Kripto KAPSAM DIŞI.**

## DEĞİŞMEZ KURALLAR
Wave-2..7 charter'ları tam metin geçerli. KURAL 1/3/12, K10, D1, R3, W1-W8, ADR-001, **ADR-013 (create_all prod'da
YASAK), ADR-013a**, OTONOM KARAR + SELF-CORRECTION. Her milestone: **canlı-gate → tag → push → MCP → milestone-log.**
Kullanıcı-görünür iş için **AYRICA KULLANIM-GATE** (gerçek veriyle uçtan uca; mock/curl yetmez). Charter Revize açık
(ürün-DNA hariç) = tag `charter-revise-w8-<N>` + MCP.

> ⚠️ **ERKEN-TAMAM YASAĞI:** "TAMAM" demeden TÜM agent'lar bitmiş + tam süit tek seferde koşulmuş olacak.
>
> ⚠️ Web asistana "ne yapayım" YASAK — **TEK istisna: sunucu para adımı (Blok B).**
>
> 🔒 **GÜVENLİK:** deploy = internete açılma. Bu wave'de her şey **production-güvenlik** gözüyle: secret sızıntısı,
> açık port, debug mode, CORS, rate limit, HTTPS zorunlu.

---

# BLOK A — DEPLOY ALTYAPISI (PARASIZ, hedef-agnostik)

**Blok gerekçesi:** rapor — canlı deploy HİÇ yapılmadı, compose yalnız statik-doğrulandı. Docker CLI dev ortamında YOK
(Wave-7 pgserver ile çözdü) — bu blok gerçek deploy hedefinde koşulacak, dev'de yapı + statik doğrulama.

### MA1 — Production Docker imajı + compose
- **Çıktı:** Multi-stage Dockerfile (backend uvicorn+gunicorn, frontend build→nginx serve). `docker-compose.prod.yml`:
  app + postgres + nginx. `.dockerignore`, sağlık-check.
- **GATE:** imaj build olur, compose config geçerli, statik güvenlik taraması (imajda secret yok, root-olmayan user).
- **D1:** 2-3 referans (FastAPI+React prod imaj deseni). · **Tag:** `milestone-93-prod-docker-imaj`.

### MA2 — Nginx reverse proxy + HTTPS
- **Çıktı:** nginx: frontend statik + `/api` backend proxy + Let's Encrypt (certbot) HTTPS + HTTP→HTTPS yönlendirme +
  güvenlik header'ları (HSTS, CSP, X-Frame).
- **GATE:** nginx config geçerli, TLS ayarları A-rating hedefli (statik doğrulama, canlı sertifika Blok B'de).
- **Tag:** `milestone-94-nginx-https`.

### MA3 — Production .env + secret yönetimi
- **Çıktı:** `.env.prod` şablonu (gerçek secret DEĞİL — placeholder). SECRET_KEY/DB/OAuth/SMTP/LLM prod değerleri nasıl
  sağlanır (belge). BUG #157 fail-fast prod'da tetikleniyor mu DOĞRULA. DEBUG=false, AUTH_ENABLED=true zorunlu.
- **GATE:** prod `.env` eksik secret ile uygulama BAŞLAMIYOR (fail-fast kanıtı). · **Tag:** `milestone-95-prod-env-secret`.

### MA4 — Deploy runbook + otomasyon
- **Çıktı:** `scripts/deploy.sh` (pull, migrate, restart, healthcheck) + geri-alma prosedürü. `docs/deployment/runbook.md`:
  sıfırdan sunucuya kurulum adımları. APScheduler cron production'da daemon olarak 7/24 KOŞAR (fiyat otomasyonu asıl buraya bağlanıyor).
- **GATE:** runbook adım adım eksiksiz, deploy.sh statik doğrulanır. · **Tag:** `milestone-96-deploy-runbook`.

---

# BLOK B — CANLI DEPLOY (Murat'ın para/sunucu kararı — İNSAN KAPISI)

**DUR.** Buraya gelince Murat'a sor: *"Blok A parasız bitti, deploy hedefe hazır. Sunucu için (1) Oracle Free Tier
deneyeyim mi (ücretsiz, kredi kartı doğrulama gerekir), yoksa (2) Hetzner €4/ay mı bağlayalım?"* Murat cevabını bekle.

### MB1 — Sunucu kurulumu + canlı deploy
- **Çıktı:** Seçilen sunucuda runbook'u ÇALIŞTIR: OS hazırla, Docker kur, repo çek, `.env.prod` gerçek secret'larla doldur
  (Murat sağlar — **secret'lar chat'e DÜŞMEZ**), compose up, Postgres migrate, HTTPS sertifika al.
- **GATE (KULLANIM-GATE canlı):** `https://<domain veya IP>` canlı, `/api/health` 200, login çalışıyor, gerçek bir işlem
  gir → cockpit güncellendi. · **Tag:** `milestone-97-canli-deploy`.

### MB2 — Canlı doğrulama turu
- **Çıktı:** Cron 7/24 daemon çalışıyor (fiyat otomasyonu PC-kapalı sorunu ÇÖZÜLDÜ — ertesi gün fiyat güncel mi kanıt).
  Tam kullanım döngüsü canlı sunucuda (Wave-5 e2e ama production). Postgres prod'da (dev SQLite değil).
- **GATE:** 24 saat sonra fiyat cron canlı yazdı mı + uçtan uca döngü canlı sunucuda yeşil. · **Tag:** `milestone-98-canli-dogrulama`.

---

# BLOK C — PWA (deploy'un HTTPS'i üzerine)

**Blok gerekçesi:** PWA installable olmak için HTTPS ister (Blok B önkoşul). Native/App Store YOK.

### MC1 — PWA temel
- **Çıktı:** `manifest.json` (ikon, tema, standalone) + service worker (offline shell, cache stratejisi) + installable kriterleri.
- **GATE:** Lighthouse PWA skoru geçer, "ana ekrana ekle" çıkıyor, offline'da app shell açılıyor. · **Tag:** `milestone-99-pwa-temel`.

### MC2 — Mobil-uyum + KULLANIM-GATE
- **Çıktı:** Responsive kontrol (cockpit + kritik paneller telefonda kullanılabilir), touch hedefleri, viewport. Capacitor
  notu: ADR'ye "ileride native istenirse Capacitor wrapper" yazılır ama uygulanmaz.
- **GATE (KULLANIM-GATE):** gerçek mobil viewport (Chrome MCP device emulation) → login → işlem gir → cockpit → uçtan uca
  çalışıyor. · **Tag:** `milestone-100-mobil-uyum`.

---

# BLOK D — KAPANIŞ
- **Çıktı:** `tam-proje-durum-raporu` güncelle (deploy + PWA bölümü). `PROJE.md` güncelle (artık canlı). **ADR-deploy +
  ADR-pwa yaz.** Wave-9 iskeleti: post-deploy GERÇEK KULLANIM ile önceliklenecek UX/refactor borçları (273'ten kalanlar).
- **MCP:** GOAL TAMAM W8 + W1 rotasyonu. Domain kararı Murat'a bırak (IP ile de canlı olur, domain opsiyonel ~yıllık ücret).
- **Tag:** `milestone-101-wave8-kapanis`.

---

## BİTİRME
**DUR.** "GOAL TAMAM WAVE-8" + kapanış raporu (kazanç/açık/borç/çelişkiler). Blok B'de sunucu adımına gelince
**İNSAN-KAPISI — Murat'ı bekle, otonom sunucu kiralama/para harcama YASAK.**

## BAŞLA
`pre-wave-8` tag + charter dosyası. Sonra MA1 (parasız altyapı).
