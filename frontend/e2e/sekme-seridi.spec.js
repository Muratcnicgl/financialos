/**
 * SEKME ŞERİDİ KAPISI — kaydırılabilir bir şerit, GERÇEKTEN kaydırılabilmeli.
 *
 * Ölçülen defekt (kullanıcı bildirimi, 9 Eyl 2026): detaylı görünümde üstteki panel
 * çubuğunun "kaydırma kısmı gitmiş; sadece klavyeyle yön tuşuna basınca kayıyor".
 * Sebep tek bir CSS kararıydı: şerit `scrollbar-width: none` ile gizlenmişti. Sonuç
 * zincirleme:
 *   - sürüklenecek bir çubuk yok,
 *   - dikey fare tekerleği yatay konteyneri kaydırmaz (tarayıcı davranışı),
 *   - geriye yalnız klavye kalır — yani fare kullanan biri 13 sekmenin son 4'üne
 *     HİÇ ulaşamaz.
 * Ders: "daha temiz görünsün" diye kaldırılan bir kontrol, o kontrolün taşıdığı
 * YETENEĞİ de kaldırır. Görünürlük bir süs değil, buradaki tek erişim yoluydu.
 *
 * Ölçülen değişmezler (390px — sığmamanın garanti olduğu genişlik):
 *   1. Şerit gerçekten taşıyor (scrollWidth > clientWidth) — kapı boşa ölçmüyor.
 *   2. Kaydırma çubuğu GİZLİ DEĞİL (`scrollbar-width` != 'none').
 *   3. Fare tekerleği şeridi yatay kaydırıyor.
 *   4. Sona kaydırınca son sekme (Hesap) gerçekten tıklanabilir hâle geliyor.
 *   5. Klavye kısayoluyla görünmeyen bir sekmeye geçilince şerit onu görünüre alıyor.
 */
import { test, expect } from '@playwright/test';

const API = process.env.E2E_API || 'http://localhost:8000';
let token;

test.use({ viewport: { width: 390, height: 844 } });

test.beforeAll(async ({ request }) => {
  const email = `serit-${Date.now()}@example.com`;
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
  // Detaylı görünüm: şeridin taşması ancak 13 sekmeyle garanti (sade modda 5 sekme
  // 390px'e sığabilir ve kapı hiçbir şey ölçmemiş olur).
  await page.addInitScript((t) => {
    localStorage.setItem('fos_access_token', t);
    localStorage.setItem('fos_gorunum_modu', 'detayli');
    // Yeni kullanicida kurulum sihirbazi kendiliginden acilir ve tam ekran modal
    // tiklamalari yer. Uygulamanin KENDI bayragi ile kapatiliyor (test ozel bir kapi
    // acmiyor): burada olculen sey serit, sihirbaz degil.
    localStorage.setItem('sihirbaz_otomatik_acildi', '1');
  }, token);
  await page.goto('/');
  await expect(page.getByRole('button', { name: /Cockpit/ }).first()).toBeVisible();
  return page.locator('nav[aria-label="Paneller"] > div > div').first();
}

test('serit tasiyor ve kaydirma cubugu GIZLI DEGIL', async ({ page }) => {
  const serit = await ac(page);

  const olcum = await serit.evaluate((el) => ({
    scrollWidth: el.scrollWidth,
    clientWidth: el.clientWidth,
    scrollbarWidth: getComputedStyle(el).scrollbarWidth,
    overflowX: getComputedStyle(el).overflowX,
    // Cubugu gizlemenin IKI yolu var: `scrollbar-width: none` ve webkit pseudo-elementini
    // `display: none` yapmak. Ikincisi de olculuyor.
    //
    // Cubugun GERCEKTEN kac piksel yer kapladigi BILEREK olculmuyor: headless Chromium
    // `--hide-scrollbars` ile kosar ve orada deger her zaman 0'dir (olculdu — gercek
    // tarayicida 6). Harness'in kendi ayarini urun kusuru diye raporlayan bir kapi,
    // yesile donsun diye kapatilir. Burada olculen sey KARAR: cubuk gizlenmedi.
    webkitCubukDisplay: getComputedStyle(el, '::-webkit-scrollbar').display,
  }));

  expect(olcum.scrollWidth, 'serit tasmiyorsa bu kapi hicbir sey olcmuyor demektir')
    .toBeGreaterThan(olcum.clientWidth);
  expect(olcum.overflowX).toBe('auto');
  expect(olcum.scrollbarWidth, 'kaydirma cubugu gizlenmis — fareyle kaydirilamaz')
    .not.toBe('none');
  expect(olcum.webkitCubukDisplay, 'webkit kaydirma cubugu display:none ile gizlenmis')
    .not.toBe('none');
});

test('fare tekerlegi seridi yatay kaydirir', async ({ page }) => {
  const serit = await ac(page);
  expect(await serit.evaluate((el) => el.scrollLeft)).toBe(0);

  await serit.hover();
  await page.mouse.wheel(0, 240);
  await expect.poll(() => serit.evaluate((el) => el.scrollLeft),
    { message: 'dikey tekerlek seridi kaydirmadi' }).toBeGreaterThan(0);
});

test('sona kaydirinca son sekme tiklanabilir olur', async ({ page }) => {
  const serit = await ac(page);
  await serit.evaluate((el) => { el.scrollLeft = el.scrollWidth; });

  const sonSekme = page.getByRole('button', { name: 'Hesap', exact: true });
  await expect(sonSekme).toBeVisible();
  await sonSekme.click();
  await expect(page.getByRole('heading', { name: 'Hesap', exact: true })).toBeVisible();
});

test('klavyeyle gecilen sekme seritte gorunur hale gelir', async ({ page }) => {
  const serit = await ac(page);

  // Cmd/Ctrl+9 → 9. sekme (Borç Stratejisi): 390px'te ilk ekranda görünmüyor.
  await page.keyboard.press('Control+9');
  const dugme = page.locator('nav[aria-label="Paneller"] button[data-aktif="1"]');
  await expect(dugme).toHaveText(/Borç Stratejisi/);

  const gorunur = await dugme.evaluate((el) => {
    const s = el.closest('[class*="overflow-x-auto"]');
    const sol = el.offsetLeft - s.scrollLeft;
    return sol >= 0 && sol + el.offsetWidth <= s.clientWidth + 1;
  });
  expect(gorunur, 'aktif sekme seridin disinda kaldi — kullanici nerede oldugunu goremez')
    .toBe(true);
});
