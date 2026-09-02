/**
 * MOBİL LANDSCAPE YÜZEY KAPISI — QA bildirimi (2 Eyl 2026): "mobil landscape bozuluyor
 * gibi, en altta olan buton".
 *
 * NEDEN AYRI DOSYA: `tema-mobil.spec.js` yalnız **390x844 PORTRAIT** ölçüyor. Telefonu yan
 * çevirmek yüksekliği 844'ten 390'a düşürür. Sabit yükseklikli kabuk (header + sekme
 * çubuğu) aynı kaldığı için içeriğe kalan alan orantısız daralır: ÖLÇÜLDÜ →
 * **viewport 390px, kabuk 114px, içeriğe kalan 236px.** QA'nın gördüğü şey tam da portrait
 * kapısının kör noktasındaydı; "mobil ölçüldü" cümlesi bugüne kadar yarımdı.
 *
 * BULUNAN DEFEKT: iki yüzer düğme (`FeedbackWidget` bottom-4, `YardimKosesi` bottom-20)
 * sağ kenarda **120px'lik** bir şerit kaplıyordu — 236px'lik içerik alanının **%51'i**.
 * O şeride denk gelen satır düğmeleri ("Sil", "Gizle", "Yeni") örtülü kalıyordu. Portrait'te
 * aynı şerit 730px'lik alanın %16'sıdır; kimsenin dikkatini çekmemesinin sebebi buydu.
 * Defekt kodda değil ORANDAYDI — ve oran ancak ikinci yön ölçülünce görünür.
 *
 * ÖLÇÜLEN DEĞİŞMEZLER:
 *   1) Kabuk bütçesi — header, viewport'un yarısından fazlasını yemez.
 *   2) **Yüzer katman bütçesi** — `position: fixed` katmanlar içerik alanının
 *      %25'inden fazlasını kaplamaz. Asıl defektin ölçüsü budur ve bir RATCHET'tir.
 *   3) Ulaşılabilirlik — hiçbir kontrol, kaydırmaya rağmen viewport dışında kalmaz.
 *   4) Yatay taşma yok · konsol hatası yok.
 *
 * BİLEREK ÖLÇÜLMEYEN — DOKUNMA HEDEFİ (44px): bu değişmez `tema-mobil.spec.js`e aittir ve
 * orada İKİ YAZILI İSTİSNASIYLA uygulanır (WCAG 2.5.8 cümle-içi kontrol · label'a sarılı
 * checkbox). İlk yazımda ölçütü buraya KOPYALADIM ama istisnaları kopyalamadım; kapı 26
 * yanlış pozitif üretti ("Nasıl kullanılır", "Hesap & verilerim" — ikisi de cümle içi
 * bağlantı). Ders (L46): bir kapının ölçütü, koruduğu sözleşmeden farklı olamaz; ikinci bir
 * kopya yazmaktansa o değişmezi sahibine bırakmak doğrudur. Dokunma hedefi zaten yöne göre
 * değişmez — aynı bileşen, aynı boyut.
 */
import { test, expect } from '@playwright/test';

// 13 panel x tam kontrol taraması 30 sn'ye sığmıyor (ilk koşum timeout'ta düşüp "flaky"
// göründü — oysa yavaştı). Süre de ölçümün parçasıdır: kısa tutulan kapı zamanla
// "zaten hep kırmızı" diye kapatılır.
test.describe.configure({ timeout: 180_000 });

const API = process.env.E2E_API || 'http://localhost:8000';
let token;

// iPhone 12/13/14 mantık boyutunun YAN çevrilmiş hâli (portrait kapısı 390x844 ölçüyor).
test.use({ viewport: { width: 844, height: 390 } });

const PANELLER = ['Cockpit', 'Koç', 'Hesaplar', 'İşlemler', 'Gelir', 'Kırmızı', 'Raporlar',
                  'Akış', 'Borç Stratejisi', 'Hedefler', 'Bütçe', 'Aile', 'Hesap'];

//: Yüzer katmanların içerik alanından yiyebileceği azami pay. Ölçülen defekt %51'di;
//: düzeltmeden sonra ~%19. Tavan bilerek arada: ratchet aşağı iner, yukarı çıkmaz.
const YUZER_TAVAN_YUZDE = 25;

test.beforeAll(async ({ request }) => {
  const email = `landscape-${Date.now()}@example.com`;
  const reg = await request.post(`${API}/api/auth/register`, {
    data: { email, password: 'Kx7#vBnq2Lm!Zp94', kvkk_consent: true },
  });
  expect(reg.status(), `register 201 — ${await reg.text()}`).toBe(201);
  token = (await reg.json()).access_token;
  // Boş ekran bir şeyi gizler: paneller DOLU ölçülür (portrait kapısıyla aynı gerekçe).
  const h = { Authorization: `Bearer ${token}` };
  await request.post(`${API}/api/accounts`, { headers: h, data: { name: 'LS Kasa', account_type: 'cash', balance: 5000 } });
  await request.post(`${API}/api/accounts`, {
    headers: h,
    data: { name: 'LS Kart', account_type: 'credit_card', balance: -3000, credit_limit: 20000, statement_day: 5, due_day: 15 },
  });
});

test.afterAll(async ({ request }) => {
  if (token) await request.delete(`${API}/api/users/me`, { headers: { Authorization: `Bearer ${token}` } });
});

/** Kabuk + yüzer katman bütçesi — landscape'te belirleyici olan iki sayı. */
const OLC_BUTCE = () => {
  const h = document.querySelector('header');
  const m = document.querySelector('main');
  const icerik = m ? Math.round(m.getBoundingClientRect().height) : 0;

  // `position: fixed` katmanlar. Alanları TOPLANMAZ (üst üste binenler iki kez sayılırdı);
  // dikey BİRLEŞİM uzunluğu alınır — yüzer düğmeler sağ kenarda dikey bir şerit oluşturuyor
  // ve zararı da o şeridin boyu kadar.
  const kutular = [];
  for (const el of document.querySelectorAll('body *')) {
    const st = getComputedStyle(el);
    if (st.position !== 'fixed') continue;
    if (st.visibility === 'hidden' || st.display === 'none' || st.opacity === '0') continue;
    if (el.closest('header')) continue;              // kabuk ayrıca ölçülüyor
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    kutular.push({
      y1: r.top, y2: r.bottom,
      etiket: `${el.tagName}.${String(el.className || '').split(' ')[0]}`,
    });
  }
  kutular.sort((a, b) => a.y1 - b.y1);
  let kapali = 0;
  let sonY = -Infinity;
  for (const k of kutular) {
    const bas = Math.max(k.y1, sonY);
    if (k.y2 > bas) { kapali += k.y2 - bas; sonY = k.y2; }
  }
  return {
    viewport: window.innerHeight,
    header: h ? Math.round(h.getBoundingClientRect().height) : null,
    icerik,
    yuzerSerit: Math.round(kapali),
    yuzerYuzde: icerik ? Math.round((kapali / icerik) * 100) : 0,
    yuzerler: kutular.map((k) => k.etiket).slice(0, 6),
  };
};

/** Görünür kontroller — indeks DOM sırasından gelir (`locator.nth` onu sayar). */
const KONTROLLER = () => {
  const gorunur = (el) => {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden'
           && st.display !== 'none' && st.opacity !== '0';
  };
  const hepsi = [...document.querySelectorAll('button, a[role="button"], [role="button"]')];
  return hepsi
    .map((el, i) => ({ el, i }))
    .filter(({ el }) => gorunur(el))
    .map(({ el, i }) => {
      const r = el.getBoundingClientRect();
      return {
        i,
        etiket: (el.getAttribute('aria-label') || el.innerText || el.title || '').trim().slice(0, 40),
        y: Math.round(r.y), h: Math.round(r.height), x: Math.round(r.x), w: Math.round(r.width),
      };
    });
};

test('landscape: yuzey kapisi (yuzer butce + ulasilabilirlik + tasma + konsol)', async ({ page }) => {
  const konsol = [];
  page.on('console', (m) => { if (m.type() === 'error') konsol.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => konsol.push(String(e).slice(0, 200)));

  await page.addInitScript((t) => { localStorage.setItem('fos_access_token', t); }, token);
  await page.goto('/');
  await expect(page.getByRole('button', { name: /Cockpit/ }).first()).toBeVisible();

  const butce = await page.evaluate(OLC_BUTCE);
  console.log('[landscape] butce:', JSON.stringify(butce));
  // KAPSAM TABANI (L11): ölçüm gerçekten sayfayı görüyor mu?
  expect(butce.header, 'header bulunamadi — kapi kor kosuyor').toBeGreaterThan(0);
  expect(butce.icerik, 'main bulunamadi — kapi kor kosuyor').toBeGreaterThan(0);

  const ihlaller = [];
  if (butce.header >= butce.viewport / 2) {
    ihlaller.push(`[kabuk] header ${butce.header}px / viewport ${butce.viewport}px — ` +
                  `icerige ${butce.icerik}px kaliyor`);
  }
  if (butce.yuzerYuzde > YUZER_TAVAN_YUZDE) {
    ihlaller.push(`[yuzer] fixed katmanlar icerigin %${butce.yuzerYuzde}'ini kapliyor ` +
                  `(${butce.yuzerSerit}px / ${butce.icerik}px, tavan %${YUZER_TAVAN_YUZDE}) ` +
                  `-> ${butce.yuzerler.join(', ')}`);
  }

  for (const ad of PANELLER) {
    const btn = page.getByRole('button', { name: new RegExp(ad) }).first();
    await expect(btn, `"${ad}" sekmesi landscape'te bulunamadi`).toBeVisible();
    await btn.click();
    await page.waitForTimeout(700);   // mount + API (portrait kapisiyla ayni bekleme)

    const tasma = await page.evaluate(() =>
      Math.round(document.documentElement.scrollWidth - document.documentElement.clientWidth));
    if (tasma > 1) ihlaller.push(`[${ad}] YATAY TASMA ${tasma}px`);

    const kontroller = await page.evaluate(KONTROLLER);
    const vy = page.viewportSize().height;
    const vx = page.viewportSize().width;
    for (const k of kontroller) {
      const disarida = k.y < -1 || k.y + k.h > vy + 1 || k.x < -1 || k.x + k.w > vx + 1;
      if (!disarida) continue;
      // Dışarıdaysa KAYDIRMA çözüyor mu? Çözüyorsa normaldir — kaydırılabilir bir kapta
      // altta kalmak beklenen davranıştır. Kırmızı olan, kaydırmanın ÇÖZMEDİĞİ durumdur.
      const el = page.locator('button, a[role="button"], [role="button"]').nth(k.i);
      let ulasildi = false;
      try {
        await el.scrollIntoViewIfNeeded({ timeout: 2000 });
        const kutu = await el.boundingBox();
        ulasildi = !!kutu && kutu.y >= -1 && kutu.y + kutu.height <= vy + 1
                   && kutu.x >= -1 && kutu.x + kutu.width <= vx + 1;
      } catch { ulasildi = false; }
      if (!ulasildi) {
        ihlaller.push(`[${ad}] ULASILAMAYAN KONTROL "${k.etiket}" (y=${k.y} h=${k.h} vy=${vy})`);
      }
    }
  }

  expect(ihlaller, `\n${ihlaller.join('\n')}\n`).toEqual([]);
  expect([...new Set(konsol)], 'konsol hatasi').toEqual([]);
});
