/**
 * A11Y-004 KAPISI (BUG #397) — İŞARET YALNIZ RENKLE TAŞINMAZ.
 *
 * Ölçülen (11 Eyl 2026): madde "signClass renk-only" diyordu. Kaynakta 6 `signClass(`
 * kullanımı var ve ALTISI da değerin yanına metinsel işaret koyuyor (`'+'`/`'−'` ya da
 * `formatPercent`, o da `+` ekler); uyarılar ikon+metin. Yani iddia bugün doğru değil —
 * ama kilitli de değildi: yeni bir kullanım işareti unutabilirdi (WCAG 1.4.1).
 *
 * Kilitlenen: her `signClass(` kullanımının hemen ardındaki 3 satırda metinsel işaret var.
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

const ISARET = /'\+'|'−'|'-'|formatPercent\(/;

describe('A11Y-004 — signClass renk-only değil', () => {
  it('her signClass kullanımının yanında metinsel işaret var', () => {
    const eksik = [];
    let sayi = 0;
    for (const f of jsxDosyalari(KOK)) {
      const satirlar = readFileSync(f, 'utf-8').split('\n');
      satirlar.forEach((s, i) => {
        if (!/signClass\(/.test(s)) return;
        sayi += 1;
        const pencere = satirlar.slice(i, i + 4).join('\n');
        if (!ISARET.test(pencere)) eksik.push(`${f.split('src')[1]}:${i + 1}`);
      });
    }
    expect(sayi, 'kapsam tabanı (L45)').toBeGreaterThanOrEqual(5);
    expect(eksik, `işaretsiz renk kodlaması:\n${eksik.join('\n')}`).toEqual([]);
  });
});
