/**
 * FE-028 KAPISI (BUG #411) — `exhaustive-deps` SUSTURMASI GEREKÇESİZ OLAMAZ.
 *
 * Ölçülen (12 Eyl 2026): 7 susturma; Cashflow'unki gerçek riskti (effect `include` Set'ini
 * okuyup bağımlılığa `includeKey`'i yazıyordu — sessiz bayat kapanış). Cashflow düzeltildi
 * (liste anahtardan türetilir, susturma kalktı). Kalan 6'sı meşru olay/açılış tetikleyicisi;
 * meşruiyet YAZILI olmalı — bir sonraki okuyan "neden?" diye kodu çözmesin.
 *
 * Kilitlenen: her `react-hooks/exhaustive-deps` susturmasının 3 satır üstünde "Neden
 * susturuldu" gerekçesi var; Cashflow'da susturma YOK; sayı ratchet'i (≤ 6).
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const KOK = join(__dirname);

function kaynaklar(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) kaynaklar(yol, out);
    else if (/\.(jsx?|js)$/.test(ad) && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

describe('FE-028 — exhaustive-deps susturmaları', () => {
  it('her susturma gerekçeli; Cashflow susturmasız; toplam ≤ 6', () => {
    const gerekcesiz = [];
    let sayi = 0;
    for (const f of kaynaklar(KOK)) {
      const satirlar = readFileSync(f, 'utf-8').split('\n');
      satirlar.forEach((s, i) => {
        if (!/eslint-disable(-next-line|-line)? react-hooks\/exhaustive-deps/.test(s)) return;
        sayi += 1;
        const rel = f.split('src')[1];
        if (/Cashflow\.jsx$/.test(f)) gerekcesiz.push(`${rel}:${i + 1} (Cashflow susturması kaldırılmıştı)`);
        const baglam = satirlar.slice(Math.max(0, i - 3), i + 1).join('\n');
        if (!/Neden susturuldu/.test(baglam)) gerekcesiz.push(`${rel}:${i + 1}`);
      });
    }
    expect(gerekcesiz, `gerekçesiz susturma:\n${gerekcesiz.join('\n')}`).toEqual([]);
    expect(sayi).toBeLessThanOrEqual(6);
    expect(sayi, 'kapsam tabanı (L45)').toBeGreaterThanOrEqual(3);
  });
});
