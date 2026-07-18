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
        // App shell (statik) precache; /api GET'leri NetworkFirst (taze veri önce, offline'da cache).
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: '/index.html',
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 50, maxAgeSeconds: 300 },
            },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
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