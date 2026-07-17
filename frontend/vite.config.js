import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// FinancialOS frontend dev server konfigurasyonu
// Proxy: /api -> http://localhost:8000  (backend uvicorn'un calistigi yer)
// Bu sayede frontend'de fetch('/api/cockpit') yazinca otomatik backend'e gider,
// CORS gerekmez, browser ayni origin'den geldigini sanar.

export default defineConfig({
  plugins: [react()],
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
  },
});