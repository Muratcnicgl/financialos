// BUG #241 e2e — "Ödendi" işaretlenen alacak GERÇEK TARAYICIDA nakde geçiyor mu?
//
// Bu bug'ı kullanıcı buldu, statik denetim değil: panel yolu ile koç yolu ayrışmıştı ve
// backend testleri iki yolu ayrı ayrı doğru sanıyordu. Kapanış kanıtı da kullanıcının
// gördüğü yerde olmalı — API cevabı değil, EKRAN.
//
// Çalıştırma: backend :8000 + frontend :5173 ayakta. `npm run e2e`.
//
// BUG #265 fix (7 Agu 2026): bu dosya KIMLIKSIZ yazilmisti (ne API cagrisinda token, ne
// sayfada oturum). CI'nin e2e isi `AUTH_ENABLED=true` ile kosuyor → `POST /api/debts`
// **401** donuyordu ve spec daha ilk adimda oluyordu. Yani bir kullanici-bildirimli para
// bug'inin (#241) "kapanis kaniti" CI'da hic yesil olmadi. Kapanis kaniti kosmuyorsa
// kanit degildir. Artik spec usage-loop ile ayni izolasyonu kullanir: kendi taze
// kullanicisi + kendi nakit hesabi, sonunda KVKK-delete ile temizlenir.
import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';
let debtId;
let baslangicNakit;
let token;
let yetki;

test.beforeAll(async ({ request }) => {
  const email = `tahsilat-${Date.now()}@example.com`;
  const reg = await request.post(`${API}/api/auth/register`, {
    data: { email, password: 'Kx7#vBnq2Lm!Zp94', kvkk_consent: true },
  });
  expect(reg.status(), `register 201 — ${await reg.text()}`).toBe(201);
  token = (await reg.json()).access_token;
  yetki = { Authorization: `Bearer ${token}` };

  // Tahsilatin dusecegi nakit hesap (app/account_rules.py varsayilan nakit hesabi secer)
  const acc = await request.post(`${API}/api/accounts`, {
    headers: yetki,
    data: { name: 'E2E Tahsilat Kasa', account_type: 'cash', balance: 5000 },
  });
  expect(acc.status(), 'nakit hesap olusturuldu').toBe(201);

  const cockpit = await (await request.get(`${API}/api/cockpit`, { headers: yetki })).json();
  baslangicNakit = cockpit.nakit_kasa;

  const r = await request.post(`${API}/api/debts`, {
    headers: yetki,
    data: { counterparty: 'E2E Tahsilat', direction: 'receivable', amount: 1234 },
  });
  expect(r.status(), 'alacak olusturuldu').toBe(201);
  debtId = (await r.json()).id;
});

test.afterAll(async ({ request }) => {
  // KVKK-delete: test-user + workspace + hesap + alacak cascade temizlenir
  if (token) await request.delete(`${API}/api/users/me`, { headers: yetki });
});

/** Sayfayi test kullanicisinin oturumuyla acar (usage-loop ile ayni yontem). */
async function girisYap(page) {
  await page.addInitScript((t) => localStorage.setItem('fos_access_token', t), token);
  await page.goto('/');
  await expect(page.getByRole('button', { name: /Cockpit/ }).first()).toBeVisible();
}

test('panelden "Ödendi" işaretlemek nakde geçer ve kullanıcıya söylenir', async ({ page, request }) => {
  await girisYap(page);

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
  const cockpit = await (await request.get(`${API}/api/cockpit`, { headers: yetki })).json();
  expect(cockpit.nakit_kasa).toBeCloseTo(baslangicNakit + 1234, 2);
});

test('kapanmış kayıt hangi hesaba işlendiğini satırında taşır ve geri alınabilir', async ({ page, request }) => {
  await girisYap(page);
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
  const oncekiCockpit = await (await request.get(`${API}/api/cockpit`, { headers: yetki })).json();
  await satir.getByTitle('Ödendi işaretini geri al').click();
  await expect(page.getByText(/geri alındı/)).toBeVisible();

  const sonraki = await (await request.get(`${API}/api/cockpit`, { headers: yetki })).json();
  expect(sonraki.nakit_kasa).toBeCloseTo(oncekiCockpit.nakit_kasa - 1234, 2);
});
