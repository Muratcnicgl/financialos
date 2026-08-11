/**
 * BUG #265 — TELEFON GENISLIGINDE + IKI TEMADA panel yuzeyi kapisi.
 *
 * Neden var: uygulamanin IKI ayri gorunumu var (koyu/acik) ve mobil strateji PWA (ADR-040),
 * ama hicbir kapi bu iki yuzeyi RENDER EDIP olcmuyordu. Olculunce cikan tablo:
 *   - 4 panel (Hedefler / Borc Stratejisi / Aile / Giris) tamamen koyu-varsayan yazilmisti;
 *     acik temada baslik `text-zinc-100` ile zinc-50 zemine dusuyordu → kontrast 1.05,
 *     yani METIN GORUNMUYORDU (bos-durum yazilari 1.27, uye satirlari 1.22).
 *   - Grafik renkleri tek temaya gore secilmisti: `#4f46e5` koyu kartta 2.82 → VARSAYILAN
 *     temada cizgi ve lejant metni okunmuyordu.
 *   - ADR-010'un "global .btn class'i gelecekteki butonlari da 44px yapar" gerekcesi
 *     dogru degildi: `.btn` KULLANMAYAN kontroller 13-42px cikiyordu ve bunu olcen yoktu.
 *
 * Ders (L27'nin bu turdaki yuzu): bir sinifi statik olarak taramak yetmez — ikinci tema
 * ancak RENDER EDILINCE olculur. Bu dosyanin ilk hali statik tarayiciydi ve 5 bulgu
 * raporlamisti; tarayici 128 kullanimin 123'unu kaciriyordu.
 *
 * Olculen degismezler (her panel x her tema, 390x844):
 *   1) Metin kontrasti >= 3:1 (WCAG AA buyuk-metin esigi; alt sinir, hedef degil)
 *   2) Yatay tasma YOK (sayfa govdesi viewport'u asmaz)
 *   3) Dokunma hedefi >= 44px (ADR-010) — iki YAZILI istisna ile:
 *        a. Cumle icindeki kontrol (WCAG 2.5.8 "inline" istisnasi): kardes metin varsa
 *           boyut satir yuksekligiyle kisitlanir, buyutmek metni bozar.
 *        b. <label> icine sarilmis checkbox/radio: tiklanabilir hedef LABEL'dir, o olculur.
 *   4) Konsol hatasi YOK.
 */
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// BUG #289: sabit adres, e2e'yi geliştiricinin CANLI backend'ine bağlıyordu
// (gerçek kullanıcıların DB'sine test verisi yazılıyordu). İzole koşum
// (`scripts/e2e_izole.py`) bu değişkenle ayrı porttaki ayrı DB'yi gösterir.
const API = process.env.E2E_API || 'http://localhost:8000';
let token;

test.use({ viewport: { width: 390, height: 844 } });   // iPhone 12/13/14 mantik genisligi

const PANELLER = ['Cockpit', 'Koç', 'Hesaplar', 'İşlemler', 'Gelir', 'Kırmızı', 'Raporlar',
                  'Akış', 'Borç Stratejisi', 'Hedefler', 'Bütçe', 'Aile', 'Hesap'];

test.beforeAll(async ({ request }) => {
  const email = `tema-${Date.now()}@example.com`;
  const reg = await request.post(`${API}/api/auth/register`, {
    data: { email, password: 'Kx7#vBnq2Lm!Zp94', kvkk_consent: true },
  });
  expect(reg.status(), `register 201 — ${await reg.text()}`).toBe(201);
  token = (await reg.json()).access_token;
  // Bos ekran bir seyi gizler: en az bir nakit + bir kart hesabi ile panelleri DOLU olcelim.
  const h = { Authorization: `Bearer ${token}` };
  await request.post(`${API}/api/accounts`, { headers: h, data: { name: 'Tema Kasa', account_type: 'cash', balance: 5000 } });
  await request.post(`${API}/api/accounts`, {
    headers: h,
    data: { name: 'Tema Kart', account_type: 'credit_card', balance: -3000, credit_limit: 20000, statement_day: 5, due_day: 15 },
  });
});

test.afterAll(async ({ request }) => {
  if (token) await request.delete(`${API}/api/users/me`, { headers: { Authorization: `Bearer ${token}` } });
});

/** Tarayici icinde kosar: tek bir panelin ihlallerini dondurur. */
const OLC = () => {
  const gorunur = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
  };
  const etiket = (el) => `${el.tagName.toLowerCase()}"${(el.textContent || '').trim().slice(0, 28)}"`;

  // ---- 1) yatay tasma ----
  const tasma = document.documentElement.scrollWidth - window.innerWidth;
  const tasanlar = [];
  if (tasma > 1) {
    for (const el of document.querySelectorAll('body *')) {
      if (!gorunur(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.right > window.innerWidth + 1) tasanlar.push(`${etiket(el)} right=${Math.round(r.right)}`);
    }
  }

  // ---- 2) dokunma hedefi (ADR-010) ----
  const cumleIcinde = (el) => {
    const p = el.parentElement;
    if (!p) return false;
    return [...p.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 0);
  };
  const olculecekHedef = (el) => {
    // istisna (b): label'a sarili checkbox/radio → tiklanabilir hedef label'dir
    if (el.tagName === 'INPUT') {
      const lab = el.closest('label');
      if (lab) return lab;
    }
    return el;
  };
  const kucuk = [];
  for (const el of document.querySelectorAll('button, a[href], select, input[type=checkbox], input[type=radio], [role=button]')) {
    if (!gorunur(el)) continue;
    if (cumleIcinde(el)) continue;                       // istisna (a): WCAG 2.5.8 inline
    const hedef = olculecekHedef(el);
    const r = hedef.getBoundingClientRect();
    if (r.width < 44 || r.height < 44) kucuk.push(`${etiket(el)} ${Math.round(r.width)}x${Math.round(r.height)}`);
  }

  // ---- 3) metin kontrasti ----
  const rgb = (s) => (s.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => {
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  // Gradient/gorsel zeminli atada hesaplanan renk saydamdir → oran ANLAMSIZ olur (₺ logosu
  // bu yuzden 1.04 raporlanmisti). Boyle bir ata gorulurse olculemez sayilir.
  const zemin = (el) => {
    let n = el;
    while (n && n !== document.documentElement) {
      const st = getComputedStyle(n);
      if (st.backgroundImage && st.backgroundImage !== 'none') return null;
      const bg = rgb(st.backgroundColor);
      if (bg.length >= 3 && (bg[3] === undefined || bg[3] > 0.5)) return bg;
      n = n.parentElement;
    }
    const b = rgb(getComputedStyle(document.body).backgroundColor);
    return b.length >= 3 ? b : [255, 255, 255];
  };
  const dusukKontrast = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!gorunur(el)) continue;
    if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 0)) continue;
    const st = getComputedStyle(el);
    const fg = rgb(st.color);
    if (fg.length < 3 || (fg[3] !== undefined && fg[3] < 0.5)) continue;
    const bg = zemin(el);
    if (!bg) continue;
    const l1 = lum(fg), l2 = lum(bg);
    const oran = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    if (oran < 3) {
      dusukKontrast.push(`"${(el.textContent || '').trim().slice(0, 30)}" ${st.color}/rgb(${bg.slice(0, 3)}) = ${oran.toFixed(2)}`);
    }
  }

  return {
    tasma,
    tasanlar: [...new Set(tasanlar)].slice(0, 5),
    kucuk: [...new Set(kucuk)],
    dusukKontrast: [...new Set(dusukKontrast)],
  };
};

// KAPSAM TABANI (L11/H25): panel listesi App.jsx'in TABS'inden TURETILEN gercek sekme
// kumesiyle ayni buyuklukte olmali. Yeni bir sekme eklenip bu listeye yazilmazsa kapi
// onu hic ziyaret etmez ve "temiz" der — kapsamsiz kapi olu kapidir.
test('kapsam tabani: panel listesi App.jsx TABS ile ayni buyuklukte', () => {
  const kok = dirname(fileURLToPath(import.meta.url));
  const kaynak = readFileSync(join(kok, '..', 'src', 'App.jsx'), 'utf8');
  const blok = kaynak.slice(kaynak.indexOf('const TABS = ['), kaynak.indexOf('];', kaynak.indexOf('const TABS = [')));
  const idler = [...blok.matchAll(/\bid:\s*'([a-z]+)'/g)].map((m) => m[1]);
  expect(idler.length, 'App.jsx TABS okunamadi').toBeGreaterThan(0);
  expect(PANELLER.length,
    `App.jsx'te ${idler.length} sekme var, kapi ${PANELLER.length} panel geziyor: ${idler.join(', ')}`,
  ).toBe(idler.length);
});

for (const tema of ['dark', 'light']) {
  test(`390px / ${tema} tema: kontrast + tasma + dokunma hedefi + konsol`, async ({ page }) => {
    const konsol = [];
    page.on('console', (m) => { if (m.type() === 'error') konsol.push(m.text().slice(0, 200)); });
    page.on('pageerror', (e) => konsol.push(String(e).slice(0, 200)));

    await page.addInitScript(([t, th]) => {
      localStorage.setItem('fos_access_token', t);
      localStorage.setItem('theme', th);
    }, [token, tema]);
    await page.goto('/');
    await expect(page.getByRole('button', { name: /Cockpit/ }).first()).toBeVisible();

    const ihlaller = [];
    for (const ad of PANELLER) {
      const btn = page.getByRole('button', { name: new RegExp(ad) }).first();
      await expect(btn, `"${ad}" sekmesi 390px'te bulunamadi`).toBeVisible();
      await btn.click();
      await page.waitForTimeout(700);   // mount + API; smoke seviyesinde kisa bekleme
      const r = await page.evaluate(OLC);
      if (r.tasma > 1) ihlaller.push(`[${ad}/${tema}] YATAY TASMA ${r.tasma}px → ${r.tasanlar.join(' ; ')}`);
      for (const k of r.kucuk) ihlaller.push(`[${ad}/${tema}] DOKUNMA HEDEFI <44px → ${k}`);
      for (const k of r.dusukKontrast) ihlaller.push(`[${ad}/${tema}] KONTRAST <3:1 → ${k}`);

      // BUG #281 (B2): geri bildirim dugmesi HER ANA ROTADA erisilebilir olmali.
      // Statik "App.jsx'te bir kez render ediliyor" tespiti YETMEZ (L29): bir panel
      // tam-ekran bir katman acsa ya da z-index/overflow dugmeyi gizlese kimse gormez.
      // Olculen sey GORUNURLUK ve TIKLANABILIRLIK.
      const gb = page.getByRole('button', { name: /Geri [Bb]ildirim/ }).first();
      if (!(await gb.isVisible().catch(() => false))) {
        ihlaller.push(`[${ad}/${tema}] GERI BILDIRIM DUGMESI GORUNMUYOR`);
      }
    }

    expect(ihlaller, `\n${ihlaller.join('\n')}\n`).toEqual([]);
    expect([...new Set(konsol)], 'konsol hatasi').toEqual([]);
  });
}
