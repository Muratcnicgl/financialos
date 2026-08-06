// BUG #241 e2e — "Ödendi" işaretlenen alacak GERÇEK TARAYICIDA nakde geçiyor mu?
//
// Bu bug'ı kullanıcı buldu, statik denetim değil: panel yolu ile koç yolu ayrışmıştı ve
// backend testleri iki yolu ayrı ayrı doğru sanıyordu. Kapanış kanıtı da kullanıcının
// gördüğü yerde olmalı — API cevabı değil, EKRAN.
//
// Çalıştırma: backend :8000 + frontend :5173 ayakta (AUTH_ENABLED=false yeterli).
//   npx playwright test e2e/tahsilat-nakde-gecer.spec.js
import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';
let debtId;
let baslangicNakit;

test.beforeAll(async ({ request }) => {
  const cockpit = await (await request.get(`${API}/api/cockpit`)).json();
  baslangicNakit = cockpit.nakit_kasa;

  const r = await request.post(`${API}/api/debts`, {
    data: { counterparty: 'E2E Tahsilat', direction: 'receivable', amount: 1234 },
  });
  expect(r.status(), 'alacak olusturuldu').toBe(201);
  debtId = (await r.json()).id;
});

test.afterAll(async ({ request }) => {
  if (debtId) await request.delete(`${API}/api/debts/${debtId}`);   // nakit etkisi de geri sarılır
});

test('panelden "Ödendi" işaretlemek nakde geçer ve kullanıcıya söylenir', async ({ page, request }) => {
  await page.goto('/');

  // Borç/Alacak sekmesi → bekleyen kayıtlar
  await page.getByRole('button', { name: /Gelir|Borç/ }).first().waitFor();
  await page.getByRole('button', { name: /Gelir\/Gider\/Borç|Gelir/ }).first().click();
  await page.getByRole('button', { name: /Borç\/Alacak/ }).click();

  const satir = page.locator('.card', { hasText: 'E2E Tahsilat' }).first();
  await expect(satir).toBeVisible();

  await satir.getByTitle('Ödendi olarak işaretle').click();

  // 1) Kullanıcıya NE OLDUĞU söylenir (bakiye sessizce değişmez)
  await expect(page.getByText(/Tahsilat işlendi/)).toBeVisible();

  // 2) Nakit GERÇEKTEN arttı (motor tarafı — ekranla aynı gerçeği görüyor mu)
  const cockpit = await (await request.get(`${API}/api/cockpit`)).json();
  expect(cockpit.nakit_kasa).toBeCloseTo(baslangicNakit + 1234, 2);
});

test('kapanmış kayıt hangi hesaba işlendiğini satırında taşır ve geri alınabilir', async ({ page, request }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Gelir\/Gider\/Borç|Gelir/ }).first().click();
  await page.getByRole('button', { name: /Borç\/Alacak/ }).click();

  // "Ödenmiş" filtresine geç (varsayılan: Bekleyen)
  await page.getByRole('combobox').filter({ hasText: /Bekleyen/ }).first()
    .selectOption('paid').catch(async () => {
      await page.locator('select').nth(1).selectOption('paid');
    });

  const satir = page.locator('.card', { hasText: 'E2E Tahsilat' }).first();
  await expect(satir).toBeVisible();
  await expect(satir.getByText(/Nakde geçti:/)).toBeVisible();

  // Geri al → nakit geri sarılır
  const oncekiCockpit = await (await request.get(`${API}/api/cockpit`)).json();
  await satir.getByTitle('Ödendi işaretini geri al').click();
  await expect(page.getByText(/geri alındı/)).toBeVisible();

  const sonraki = await (await request.get(`${API}/api/cockpit`)).json();
  expect(sonraki.nakit_kasa).toBeCloseTo(oncekiCockpit.nakit_kasa - 1234, 2);
});
