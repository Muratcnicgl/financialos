import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';  // MC1 (Wave-8): PWA — installable + offline shell

// FinancialOS frontend dev server konfigurasyonu
// Proxy: /api -> http://localhost:8000  (backend uvicorn'un calistigi yer)
// Bu sayede frontend'de fetch('/api/cockpit') yazinca otomatik backend'e gider,
// CORS gerekmez, browser ayni origin'den geldigini sanar.

export default defineConfig({
  plugins: [
    react(),
    // MC1 (Wave-8): PWA — manifest + workbox service worker (offline app shell + API network-first).
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/icon-192.png', 'icons/icon-512.png'],
      manifest: {
        name: 'FinancialOS',
        short_name: 'FinancialOS',
        description: 'Kişisel finansal işletim sistemi — kural motoru karar verir, koç açıklar.',
        lang: 'tr',
        theme_color: '#0f172a',
        background_color: '#0f172a',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/maskable-192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
          { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // App shell (statik) precache. API YANITLARI ONBELLEGE ALINMAZ — bkz. BUG #288.
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: '/index.html',
        // BUG #288: `/api/*` navigasyonlarina index.html DONULMEZ. Aksi halde bir API
        // yolu tarayicida acildiginda JSON yerine uygulama HTML'i doner ve hata teshisi
        // yaniltici olur.
        navigateFallbackDenylist: [/^\/api\//],
        // BUG #288 — API ICIN ONBELLEK YOK (runtimeCaching KASTEN BOS).
        //
        // Onceki hali `/api/*` icin NetworkFirst + networkTimeoutSeconds: 5 idi. Canlida
        // ilk gercek kullanimda coktu: kullanici giris yapti, Cockpit yuklenemedi ve
        // konsolda `FetchEvent.respondWith received an error: no-response` cikti.
        // Mekanizma: 5 sn'de yanit gelmezse NetworkFirst ONBELLEGE duser; onbellekte o
        // istek YOKSA Workbox `no-response` firlatir ve istek TAMAMEN olur. Yani zaman
        // asimi bir yedek degil, ARIZA uretiyordu.
        //
        // 5 sn zaten yanlis bir tavandi: koc ucu IKI LLM cagrisi surer (10-40 sn, bkz.
        // app/capacity.py yavas-yol tavanlari) ve tunel yolu ek gecikme ekler.
        //
        // Tavani buyutmek de dogru cozum DEGIL: bu bir finans uygulamasi ve API yanitlari
        // BAKIYE tasiyor. Onbellekten servis edilen bir bakiye, kullaniciya TAZE gibi
        // gorunur — projenin BUG #239'da kapattigi hatanin ta kendisi. Ustelik yanitlar
        // tarayici onbelleginde kalir; ayni cihazi kullanan baska biri okuyabilir (BUG #180).
        //
        // Karar: app shell (JS/CSS/ikon) onbellege alinir -> uygulama cevrimdisi ACILIR ve
        // DURUST bir "baglanti yok" hatasi gosterir. Veri asla onbellekten gelmez.
        runtimeCaching: [],
      },
    }),
  ],
  server: {
    port: 5173,
    // Dev'de tarayıcıyı kendiliğinden açmak kolaylıktır; OTOMASYONDA değildir. Her e2e
    // koşumu bir vite başlatır ve `open:true` geliştiricinin Chrome'unda yeni bir sekme
    // açar — arka arkaya koşumlar sekme yığar (ölçüldü). `scripts/e2e_izole.py` ve CI
    // bu değişkenle kapatır.
    open: process.env.VITE_OTOMATIK_AC !== '0',
    proxy: {
      '/api': {
        // BUG #289: hedef sabitken `npm run e2e` GELİŞTİRİCİNİN CANLI backend'ine
        // (ve dolayısıyla gerçek kullanıcıların veritabanına) gidiyordu. Testin
        // yazdığı kullanıcı/işlem, canlı defterde gerçek kayıtların yanına düşer.
        // Hedef artık env ile yönlendirilebilir; izole e2e koşumu ayrı porttaki
        // ayrı DB'li bir backend'i gösterir (`npm run e2e:izole`).
        target: process.env.VITE_API_HEDEF || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,  // M35 (FE-032/PERF-020): prod build'de kaynak sızıntısı önlenir
  },
  // M64: component testleri için jsdom + testing-library (regresyon ağı)
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.js'],
    exclude: ['**/node_modules/**', 'e2e/**'],  // M69: e2e Playwright'e ait, vitest almasın
  },
});