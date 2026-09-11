/**
 * A11Y-017 + A11Y-012 KAPISI (BUG #392).
 *
 * Ölçülen (11 Eyl 2026): `document.title` `index.html`deki sabit "FinancialOS"tu — hangi
 * panelde olunduğu başlıktan okunamıyordu (WCAG 2.4.2). Tek `type="range"` (DebtStrategy)
 * `label`'a bağlı değildi ve değerini yalnız sayı olarak duyuruyordu (WCAG 4.1.2).
 *
 * Kilitlenen: başlık SEKMELER'den türetilir ve App sekme değişince yazar; her range girdisi
 * label'a bağlı (id ↔ htmlFor) ya da aria-label taşır, ve aria-valuetext verir.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { sayfaBasligi, SEKMELER, URUN_ADI } from './lib/sekmeler.js';

const KOK = join(__dirname);

function jsxDosyalari(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) jsxDosyalari(yol, out);
    else if (ad.endsWith('.jsx') && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

describe('A11Y-017 — belge başlığı aktif paneli söyler', () => {
  it('her sekme için "Etiket · Ürün" üretir; basit modda basit etiket', () => {
    for (const s of SEKMELER) {
      expect(sayfaBasligi(s.id, false)).toBe(`${s.label} · ${URUN_ADI}`);
      if (s.basitEtiket) expect(sayfaBasligi(s.id, true)).toBe(`${s.basitEtiket} · ${URUN_ADI}`);
    }
    expect(sayfaBasligi('yok-boyle-sekme', false)).toBe(URUN_ADI);
  });

  it('App sekme değişince document.title yazar (kaynak bağı)', () => {
    const src = readFileSync(join(KOK, 'App.jsx'), 'utf-8');
    expect(src).toMatch(/document\.title = sayfaBasligi\(activeTab, basit\)/);
    expect(src).toMatch(/\}, \[activeTab, basit\]\);/);
  });
});

describe('A11Y-012 — range girdileri adlandırılmış ve değer metni var', () => {
  it('her type="range" için label bağı + aria-valuetext', () => {
    let sayi = 0;
    for (const f of jsxDosyalari(KOK)) {
      const src = readFileSync(f, 'utf-8');
      const re = /<input\b[^>]*type="range"[^>]*>/gs;
      let m;
      while ((m = re.exec(src)) !== null) {
        sayi += 1;
        const tag = m[0];
        const id = tag.match(/\bid="([^"]+)"/)?.[1];
        const adli = (id && src.includes(`htmlFor="${id}"`)) || /aria-label=/.test(tag);
        expect(adli, `${f.split('src')[1]}: range girdisi adsız`).toBe(true);
        expect(tag, `${f.split('src')[1]}: aria-valuetext yok`).toMatch(/aria-valuetext=/);
      }
    }
    expect(sayi, 'kapsam tabanı: en az bir range girdisi (L45)').toBeGreaterThanOrEqual(1);
  });
});
