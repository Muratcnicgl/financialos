// M69 (Wave-5) — Kullanım döngüsü e2e + 13 panel smoke.
// Gerekçe (tam-proje-durum-raporu §B24): transactions=0, döngü 74 gün hiç işletilmedi;
// M65-M66'da elle kanıtlandı. Bu harness onu OTOMATİK + tekrarlanabilir yapar → bir daha görünmez olmasın.
//
// İzolasyon (D1): her koşum kendi taze test-user'ıyla (M62: kendi personal workspace) çalışır,
// Murat'ın gerçek verisine dokunmaz; sonunda KVKK-delete ile temizlenir.
import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';
let token;

test.beforeAll(async ({ request }) => {
  const email = `e2e-${Date.now()}@example.com`;  // .local reserved (EmailStr reddediyor)
  const reg = await request.post(`${API}/api/auth/register`, {
    data: { email, password: 'e2e-guclu-sifre-9999', kvkk_consent: true },
  });
  expect(reg.status(), 'register 201').toBe(201);
  token = (await reg.json()).access_token;
  // döngü için nakit hesap (harcama düşecek)
  const acc = await request.post(`${API}/api/accounts`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: 'E2E Kasa', account_type: 'cash', balance: 5000 },
  });
  expect(acc.status(), 'account 201').toBe(201);
});

test.afterAll(async ({ request }) => {
  // KVKK-delete: test-user + workspace + hesap + işlem cascade temizlenir
  if (token) {
    await request.delete(`${API}/api/users/me`, { headers: { Authorization: `Bearer ${token}` } });
  }
});

async function login(page) {
  await page.addInitScript((t) => localStorage.setItem('fos_access_token', t), token);
  await page.goto('/');
  await expect(page.getByRole('button', { name: /Cockpit/ }).first()).toBeVisible();
}

test('kullanım döngüsü: harcama gir → cockpit güncellenir (UI→DB→rules_engine)', async ({ page, request }) => {
  await login(page);

  // İşlemler → hızlı giriş harcama
  await page.getByRole('button', { name: /İşlemler/ }).first().click();
  const quick = page.getByPlaceholder(/Hızlı giriş/);
  await expect(quick).toBeVisible();
  await quick.fill('300 fatura');
  await quick.press('Enter');
  await expect(page.getByText(/Toplam 1 işlem/)).toBeVisible();

  // Sonuç rules_engine'de: nakit 5000 → 4700 (cockpit API, döngünün hesap ayağı)
  const ck = await request.get(`${API}/api/cockpit`, { headers: { Authorization: `Bearer ${token}` } });
  const cockpit = await ck.json();
  expect(Number(cockpit.nakit_kasa)).toBe(4700);
});

test('panel smoke: 13 panel konsol hatası ÜRETMEZ (B18-5)', async ({ page }) => {
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));

  await login(page);
  const panels = ['Koç', 'Hesaplar', 'İşlemler', 'Gelir', 'Kırmızı', 'Raporlar',
                  'Akış', 'Borç Stratejisi', 'Hedefler', 'Bütçe', 'Aile', 'Cockpit'];
  for (const name of panels) {
    await page.getByRole('button', { name: new RegExp(name) }).first().click();
    await page.waitForTimeout(500);  // mount + API; smoke için kısa (D1 hard-wait minimal)
  }
  // Recharts width(-1) warning'i (BUG #059) 'error' değil 'warning' → errors'a düşmez.
  expect(errors, `konsol hataları: ${errors.join(' | ')}`).toEqual([]);
});
