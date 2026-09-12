/**
 * UX-040 KAPISI (BUG #433) — KLAVYE ODAK HALKASI ÖLÇÜLÜYOR.
 *
 * Ölçülen (12 Eyl 2026): `.btn`/`.sekme`/`.input` odak halkası taşıyordu ama `focus:` ile —
 * fareyle tıklayan da halkayla kalıyordu; ve `outline-none` yazan 11 yerin biri (komut
 * paleti girdisi) hiçbir görünür odak vermiyordu. Madde "focus-visible halkaları
 * ölçülmüyor" diyordu; artık ölçülüyor.
 *
 * Kilitlenen: `.btn` ve `.sekme` `focus-visible:ring-2`; `.input` `focus:ring-2` (metin
 * kutusuna fareyle girilse de halka); JSX'te `outline-none` yalnız `tabIndex={-1}` diyalog
 * kabında ya da yanında bir `ring-2` varyantıyla.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const KOK = join(__dirname);

function jsxDosyalari(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) jsxDosyalari(yol, out);
    else if (ad.endsWith('.jsx') && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

function cssBlogu(css, secici) {
  const i = css.indexOf(`${secici} {`);
  expect(i, `${secici} bloğu index.css'te yok`).toBeGreaterThanOrEqual(0);
  return css.slice(i, css.indexOf('}', i));
}

describe('UX-040 — odak halkası', () => {
  const css = readFileSync(join(KOK, 'index.css'), 'utf-8');

  it('.btn ve .sekme klavye odağında halka (focus-visible), .input her odakta', () => {
    expect(cssBlogu(css, '.btn')).toMatch(/focus-visible:ring-2/);
    expect(cssBlogu(css, '.sekme')).toMatch(/focus-visible:ring-2/);
    expect(cssBlogu(css, '.input')).toMatch(/focus:ring-2/);
  });

  it('outline-none yalnız diyalog kabında (tabIndex -1) ya da ring varyantıyla', () => {
    const ihlal = [];
    let sayi = 0;
    for (const f of jsxDosyalari(KOK)) {
      const satirlar = readFileSync(f, 'utf-8').split('\n');
      satirlar.forEach((s, i) => {
        if (!/\boutline-none\b/.test(s)) return;
        sayi += 1;
        const pencere = satirlar.slice(Math.max(0, i - 4), i + 2).join('\n');
        const kap = /tabIndex=\{-1\}/.test(pencere) && /role="dialog"/.test(pencere);
        const halka = /(focus|focus-visible):ring-2/.test(s);
        if (!kap && !halka) ihlal.push(`${f.split('src')[1]}:${i + 1}`);
      });
    }
    expect(sayi, 'kapsam tabanı (L45)').toBeGreaterThanOrEqual(8);
    expect(ihlal, 'görünür odağı olmayan outline-none').toEqual([]);
  });
});
