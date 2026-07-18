# ADR-040 — PWA + mobil-uyum (Progressive Web App, native yerine) — Wave-8 Blok C

**Tarih:** 18 Temmuz 2026 · **Durum:** Kabul edildi, kod TAMAM + STATİK-DOĞRULANDI, canlı PWA-gate (HTTPS) deploy bekliyor
(Wave-8 MC1-MC2) · **İlgili:** ADR-009 (PWA→RN yol haritası, bu ADR PWA'yı kesinleştirir), ADR-011 (Apple HIG 44px touch),
ADR-039 (deploy — PWA HTTPS gerektirir), BUG #059 (Recharts/CSS)

## Bağlam
Wave-8 ÜRÜN-DNA'sı (Murat, 18 Tem): **"MOBİL = PWA. Native/App Store/Apple hesabı ($99/yıl) KAPSAM DIŞI. Capacitor kapısı
açık bırakılır, kullanılmaz."** ADR-009 (Wave-2) "PWA önce, gerekirse React Native" demişti; Wave-8 bunu kesinleştirir:
tek-kullanıcı + aile (2-6 kişi) için PWA yeterli — kurulum sürtünmesi düşük, tek kod tabanı, mağaza-onayı yok, veri
egemenliği korunur. PWA'nın installable + offline kriterleri **HTTPS zorunlu** → canlı gate deploy'a (ADR-039) bağlı.

## Karar

### 1. PWA temel — `vite-plugin-pwa` (generateSW / workbox)
- **`manifest.webmanifest`:** name/short_name "FinancialOS", `display: standalone`, theme+background `#0f172a`
  (index.html `theme-color` ile tutarlı), `start_url: /`, `scope: /`, `lang: tr`.
- **İkonlar** (`frontend/public/icons/`, Pillow ile üretildi, ₺ marka): 192 + 512 **plus maskable 192/512**. Maskable şart:
  Android adaptive-icon safe-zone olmadan PWA "install edilebilir" kriterini geçmez.
- **Service worker (workbox):**
  - **App shell precache** (`**/*.{js,css,html,svg,png,woff2}`, `navigateFallback: /index.html`) → offline'da kabuk açılır.
  - **`/api/*` NetworkFirst** (5sn timeout, 5dk/50-entry cache): finansal veri **tazelik önce**, çevrimdışıda son bilinen
    değer gösterilir (StaleWhileRevalidate DEĞİL — bayat bakiye göstermek yanıltıcı; NetworkFirst taze varken taze verir).
  - `registerType: autoUpdate` (yeni sürüm sessiz güncellenir).
- **iOS (`index.html`):** Safari manifest'i tam desteklemez → `apple-mobile-web-app-capable/status-bar-style/title` +
  `apple-touch-icon` (192) ile "ana ekrana ekle" standalone çalışır.

### 2. Mobil-uyum — responsive kırılma düzeltmeleri (390px/iPhone)
- **Bağlam:** `<main>` üzerinde `overflow-x-hidden` (App.jsx) taşan içeriği **gizler** (sayfa yatay kaymaz ama içerik
  kırpılır, okunamaz) → taşma = "kritik veri görünmüyor" bug'ı. `.btn`/`.btn-icon` zaten 44px min (index.css) → yalnız
  **ham `<button>`'lar** ADR-011 ihlali.
- **P0:** IncomeDebt iç sekmeler `overflow-x-auto` (ana tab bar deseni); MetricCard değer `text-lg sm:text-2xl` +
  **truncate kaldırıldı** (net-değer 2-kolon gridde kesilmez).
- **P1:** DebtStrategy `grid-cols-1 sm:grid-cols-3` + isim `truncate min-w-0`; 7 ham `<button>` → `min-w/h-[44px]` +
  merkezleme (ADR-011); WorkspaceSwitcher `max-w-[100px] sm:max-w-[140px]`.
- **Mobile-first:** grid'ler `grid-cols-1 → sm:grid-cols-N`, yatay-kaydırma taşma çözümü olarak (kırpma değil).

### 3. Native kapısı — açık, kullanılmaz
Capacitor/RN yolu kod-değişikliği gerektirmeyecek şekilde bilinçli bırakıldı (SPA + PWA manifest zaten native-wrap'a hazır).
Bu Wave'de **kullanılmaz** — Apple $99/App Store onay/ayrı kod-tabanı maliyeti tek-kullanıcı+aile için gerekçesiz.

## D1 — Sektör referansları
vite-plugin-pwa (Vite resmi PWA eklentisi) · workbox NetworkFirst (Google — API tazelik>offline dengesi) · maskable icon
(web.dev PWA install kriteri) · apple-* meta (Apple Safari add-to-home) · Tailwind mobile-first breakpoint · Apple HIG 44px
min touch (ADR-011).

## Sonuç
PWA kodu + mobil responsive **TAMAM + statik-doğrulandı** (`npm run build` → sw.js/manifest/registerSW üretiliyor, 4 ikon
precache, 63 vitest regresyon yok). **CANLI GATE'ler HTTPS deploy bekliyor** (ADR-039, Murat sunucu-kapısı): Lighthouse PWA
skoru, "ana ekrana ekle", offline app-shell, gerçek mobil viewport uçtan uca (login→işlem→cockpit). Deploy sonrası bu ADR
"canlı doğrulandı" notuyla güncellenecek — körlemesine "PWA çalışıyor" DENMEZ.
