/**
 * DVIZ-006 KAPISI (BUG #453) — GRAFİK RENKLERİ TEK KAYNAKTAN, TEMA-NÖTR.
 *
 * Ölçülen (13 Eyl 2026): BUG #265 grafik renklerini `lib/grafikRenkleri.js`'e toplamıştı (her
 * renk iki temada ≥ 3:1) ama üç yerde literal hex geri sızmıştı: AylikSeri (referans çizgisi
 * ve iki bar), Sankey düğüm renkleri (yorumdaki token adları paletle uyuşmuyordu), Raporlar
 * takvim noktası. Grid/eksen: `IZGARA`/`EKSEN` (BUG #265) — dark mode'da görünmez grid iddiası
 * bugün için yanlış; kilit yoktu.
 *
 * Kilitlenen: `.jsx` ürün dosyalarında grafik/nokta rengi olarak literal hex yok (yalnız
 * `grafikRenkleri.js` tanımlar); AkisSparkline `currentColor`/Tailwind sınıfı kullanır (muaf).
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

describe('DVIZ-006 — grafik rengi tek kaynak', () => {
  it('ürün .jsx dosyalarında literal hex renk yok', () => {
    const ihlal = [];
    for (const f of jsxDosyalari(KOK)) {
      readFileSync(f, 'utf-8').split('\n').forEach((s, i) => {
        if (/^\s*(\/\/|\*|\/\*)/.test(s)) return;   // yorum satırı
        if (/['"]#[0-9a-fA-F]{6}['"]/.test(s)) ihlal.push(`${f.split('src')[1]}:${i + 1}`);
      });
    }
    expect(ihlal).toEqual([]);
  });

  it('grid/eksen renkleri tek kaynaktan (IZGARA/EKSEN) kullanılıyor', () => {
    const rep = readFileSync(join(KOK, 'panels', 'Reports.jsx'), 'utf-8');
    expect(rep).toMatch(/stroke=\{IZGARA\}/);
    expect(rep).toMatch(/EKSEN/);
    const ay = readFileSync(join(KOK, 'components', 'AylikSeri.jsx'), 'utf-8');
    expect(ay).toMatch(/stroke=\{IZGARA\}/);
  });
});

describe('DVIZ-001 — yatırım değeri kendi ekseninde (BUG #457)', () => {
  it('net değer serileri "net", yatırım "yatirim" (sağ) eksenine bağlı', () => {
    const rep = readFileSync(join(KOK, 'panels', 'Reports.jsx'), 'utf-8');
    expect(rep).toMatch(/<YAxis\s+yAxisId="yatirim"\s+orientation="right"/);
    expect((rep.match(/yAxisId="net"/g) || []).length).toBeGreaterThanOrEqual(4);   // eksen + referans + 2 seri
    const i = rep.indexOf('dataKey="investment_value"');
    expect(rep.slice(i - 60, i)).toMatch(/yAxisId="yatirim"/);
  });
});

describe('DVIZ-012 — net değer bileşenleri (BUG #458)', () => {
  it('bileşen serisi: varlıklar +, borçlar − işaretli; Reports toggle ve bileşen bileşeni bağlı', async () => {
    const { bilesenSerisi } = await import('./components/NetDegerBilesenleri.jsx');
    const [s] = bilesenSerisi([{ date: '2026-09-12', cash: 1000, investment_value: 500, receivables: 150, card_debt: 300, loan_debt: 200, net_worth_full: 1150 }]);
    expect(s).toEqual({ date: '2026-09-12', cash: 1000, investment_value: 500, receivables: 150, card_debt_neg: -300, loan_debt_neg: -200, net_worth_full: 1150 });
    const rep = readFileSync(join(KOK, 'panels', 'Reports.jsx'), 'utf-8');
    expect(rep).toMatch(/aria-pressed=\{bilesenGorunumu\}/);
    expect(rep).toMatch(/<NetDegerBilesenleri items=\{trendItems\}/);
  });
});
