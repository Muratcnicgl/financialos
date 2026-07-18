// M69 (Wave-5) — Playwright e2e: kullanım döngüsü + panel smoke otomasyonu.
// D1 (research-log): kritik-akış + smoke, role-locator, web-first assert, retries:2, trace-on-failure.
// Çalıştırma: backend :8000 (AUTH_ENABLED=true) + frontend :5173 ayakta olmalı. `npm run e2e`.
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 2,                      // D1: flaky ağ/LLM'siz deterministik akış; 2 retry
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',    // D1: başarısızlıkta trace
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
