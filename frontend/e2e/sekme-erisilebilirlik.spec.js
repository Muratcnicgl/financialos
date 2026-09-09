/**
 * SEKME ÇUBUĞU ERİŞİLEBİLİRLİK KAPISI — A11Y-002.
 *
 * Maddenin kendi uyarısı vardı ve 9 Eyl 2026'da ÖLÇÜLDÜ: `role="tab"` eklemek
 * erişilebilir rolü değiştirir ve `getByRole('button')` ile sorgulayan testleri kırar.
 * O tur rol eklenmiş, üç e2e kapısı anında kırmızıya dönmüş ve rol geri alınmıştı;
 * madde "aynı turda e2e sorguları da taşınmalı" şartıyla açık bırakıldı. Bu tur onu
 * kapatıyor: örüntünün TAMAMI kuruldu ve sorgular `getByRole('tab')`e taşındı.
 *
 * NEDEN ROL TEK BAŞINA YETMEZ: ARIA sekme örüntüsü bir SÖZLEŞMEDİR. Ekran okuyucu
 * "sekme, 3/13, seçili" dediğinde kullanıcı ok tuşlarıyla gezinebileceğini varsayar.
 * Rolü verip klavyeyi vermemek, çalışmayan bir vaat üretir — bu, hiç rol vermemekten
 * kötüdür. Bu yüzden ölçülen şey rolün VARLIĞI değil, örüntünün DAVRANIŞIDIR.
 *
 * Ölçülen değişmezler:
 *   1. role="tablist" + 13 role="tab"; yalnız biri aria-selected="true".
 *   2. Roving tabindex: seçili sekme 0, diğerleri -1 (Tab sırası tek durak).
 *   3. Ok tuşları ODAĞI taşır, SEÇİMİ değiştirmez (manuel etkinleştirme).
 *   4. Enter seçimi değiştirir.
 *   5. Home/End ilk/son sekmeye gider.
 *   6. Seçili sekmenin karşılığı bir role="tabpanel" var ve aria-labelledby ile
 *      o sekmeyi gösteriyor; sekme de aria-controls ile paneli gösteriyor.
 */
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API || 'http://localhost:8000';
let token;

test.use({ viewport: { width: 1280, height: 900 } });

test.beforeAll(async ({ request }) => {
  const email = `a11y-${Date.now()}@example.com`;
  const reg = await request.post(`${API}/api/auth/register`, {
    data: { email, password: 'Kx7#vBnq2Lm!Zp94', kvkk_consent: true },
  });
  expect(reg.status(), `register 201 — ${await reg.text()}`).toBe(201);
  token = (await reg.json()).access_token;
});

test.afterAll(async ({ request }) => {
  if (token) await request.delete(`${API}/api/users/me`, { headers: { Authorization: `Bearer ${token}` } });
});

async function ac(page) {
  await page.addInitScript((t) => {
    localStorage.setItem('fos_access_token', t);
    localStorage.setItem('fos_gorunum_modu', 'detayli');
    localStorage.setItem('sihirbaz_otomatik_acildi', '1');
  }, token);
  await page.goto('/');
  await expect(page.getByRole('tab', { name: /Cockpit/ }).first()).toBeVisible();
}

test('tablist + tab rolleri ve tek secili sekme', async ({ page }) => {
  await ac(page);
  const tablist = page.getByRole('tablist');
  await expect(tablist).toHaveCount(1);

  const sekmeler = page.getByRole('tab');
  await expect(sekmeler).toHaveCount(13);

  const secili = page.locator('[role="tab"][aria-selected="true"]');
  await expect(secili).toHaveCount(1);
  await expect(secili).toHaveText(/Cockpit/);
});

test('roving tabindex: Tab sirasinda tek durak var', async ({ page }) => {
  await ac(page);
  const durum = await page.evaluate(() =>
    [...document.querySelectorAll('[role="tab"]')].map((e) => e.tabIndex));
  expect(durum.filter((x) => x === 0), 'tam bir sekme Tab sirasinda olmali').toHaveLength(1);
  expect(durum.filter((x) => x === -1)).toHaveLength(12);
  // Tab sirasindaki durak SECILI sekme olmali
  const sifirOlan = await page.evaluate(() =>
    document.querySelector('[role="tab"][tabindex="0"]').getAttribute('aria-selected'));
  expect(sifirOlan).toBe('true');
});

test('ok tuslari ODAGI tasir, SECIMI degistirmez (manuel etkinlestirme)', async ({ page }) => {
  await ac(page);
  await page.getByRole('tab', { name: /Cockpit/ }).focus();

  await page.keyboard.press('ArrowRight');
  const odak1 = await page.evaluate(() => document.activeElement.textContent.trim());
  expect(odak1).toMatch(/Koç/);
  // seçim HÂLÂ Cockpit
  await expect(page.locator('[role="tab"][aria-selected="true"]')).toHaveText(/Cockpit/);

  await page.keyboard.press('ArrowLeft');
  const odak2 = await page.evaluate(() => document.activeElement.textContent.trim());
  expect(odak2).toMatch(/Cockpit/);
});

test('Enter secimi degistirir', async ({ page }) => {
  await ac(page);
  await page.getByRole('tab', { name: /Cockpit/ }).focus();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Enter');
  await expect(page.locator('[role="tab"][aria-selected="true"]')).toHaveText(/Koç/);
});

test('Home ve End ilk/son sekmeye gider', async ({ page }) => {
  await ac(page);
  await page.getByRole('tab', { name: /Cockpit/ }).focus();

  await page.keyboard.press('End');
  expect(await page.evaluate(() => document.activeElement.textContent.trim())).toMatch(/Hesap/);

  await page.keyboard.press('Home');
  expect(await page.evaluate(() => document.activeElement.textContent.trim())).toMatch(/Cockpit/);
});

test('tabpanel var ve secili sekmeyle karsilikli bagli', async ({ page }) => {
  await ac(page);
  const bag = await page.evaluate(() => {
    const sekme = document.querySelector('[role="tab"][aria-selected="true"]');
    const panel = document.querySelector('[role="tabpanel"]');
    return {
      panelVar: !!panel,
      panelId: panel && panel.id,
      sekmeControls: sekme && sekme.getAttribute('aria-controls'),
      panelLabelledby: panel && panel.getAttribute('aria-labelledby'),
      sekmeId: sekme && sekme.id,
      panelOdaklanabilir: panel && panel.tabIndex === 0,
      // secili OLMAYAN sekmeler olmayan bir id'yi gostermemeli
      olusuzControls: [...document.querySelectorAll('[role="tab"][aria-selected="false"]')]
        .filter((e) => e.getAttribute('aria-controls')).length,
    };
  });
  expect(bag.panelVar).toBe(true);
  expect(bag.sekmeControls).toBe(bag.panelId);
  expect(bag.panelLabelledby).toBe(bag.sekmeId);
  expect(bag.panelOdaklanabilir).toBe(true);
  expect(bag.olusuzControls,
    'secili olmayan sekme, DOM\'da olmayan bir panele isaret etmemeli').toBe(0);
});
