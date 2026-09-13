/**
 * A11Y-013 KAPISI (BUG #451) — HER GRAFİĞİN VERİDEN TÜREYEN METİN ALTERNATİFİ VAR.
 *
 * Ölçülen (13 Eyl 2026): 6 Recharts grafiği (`ResponsiveContainer`) `role="img"`/etiket
 * taşımıyordu; ekran okuyucu için grafik yoktu (WCAG 1.1.1). Özetler `lib/grafikOzeti.js`:
 * sayılar aynı biçimlendiriciyle, en fazla 5 kalem, boş veride "veri yok".
 *
 * Kilitlenen: kaynakta her `ResponsiveContainer`ın en yakın sarmalayıcısı `role="img"` +
 * `aria-label`; özet fonksiyonları gerçek sayıları söyler ve boş veride bozulmaz.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { kategoriOzeti, netDegerOzeti, aylikSeriOzeti, bakiyeTrendiOzeti, sankeyOzeti } from './lib/grafikOzeti.js';

const KOK = join(__dirname);
function jsxDosyalari(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) jsxDosyalari(yol, out);
    else if (ad.endsWith('.jsx') && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

describe('A11Y-013 — grafik metin alternatifi', () => {
  it('her ResponsiveContainer role=img + aria-label sarmalayıcı içinde', () => {
    const ihlal = []; let sayi = 0;
    for (const f of jsxDosyalari(KOK)) {
      const L = readFileSync(f, 'utf-8').split('\n');
      L.forEach((s, i) => {
        if (!/<ResponsiveContainer\b/.test(s)) return;
        sayi += 1;
        const once = L.slice(Math.max(0, i - 3), i).join('\n');
        if (!/role="img"/.test(once) || !/aria-label=/.test(once)) ihlal.push(`${f.split('src')[1]}:${i + 1}`);
      });
    }
    expect(sayi, 'kapsam tabanı (L45)').toBeGreaterThanOrEqual(6);
    expect(ihlal).toEqual([]);
  });

  it('özetler gerçek sayıları söyler, boş veride bozulmaz', () => {
    expect(kategoriOzeti([{ category: 'market', total: 1500 }, { category: 'kira', total: 500 }], 2000))
      .toBe('Kategori dağılımı, 2 kalem: market 1.500,00 TL (%75), kira 500,00 TL (%25)');
    expect(kategoriOzeti([], 0)).toMatch(/veri yok/);
    expect(netDegerOzeti([{ net_worth_seen: 10, net_worth_full: 12 }, { net_worth_seen: 20, net_worth_full: 25 }]))
      .toMatch(/görülen 10,00 TL → 20,00 TL, tam 12,00 TL → 25,00 TL/);
    expect(aylikSeriOzeti([{ label: 'Eylül 2026', total_income: 100, total_expense: 40 }])).toMatch(/Eylül 2026: gelir 100,00 TL, gider 40,00 TL/);
    expect(bakiyeTrendiOzeti([{ balance: 5, crunch: false }, { balance: -2, crunch: true }])).toMatch(/en düşük -2,00 TL, en yüksek 5,00 TL, 1 sıkışma günü/);
    expect(sankeyOzeti({ nodes: [{ type: 'income' }, { type: 'cash' }, { type: 'expense' }],
                          links: [{ source: 0, target: 1, value: 100 }, { source: 1, target: 2, value: 30 }] }))
      .toBe('Nakit akış diyagramı: 1 giriş kalemi 100,00 TL, 1 çıkış kalemi 30,00 TL');
    const uzun = Array.from({ length: 8 }, (_, i) => ({ category: `k${i}`, total: 1 }));
    expect(kategoriOzeti(uzun, 8)).toMatch(/8 kalem: .*, …$/);
  });
});
