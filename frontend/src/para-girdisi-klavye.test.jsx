/**
 * UX-016 KAPISI (BUG #422) — PARA GİRDİLERİ `type="text" inputMode="decimal"`.
 *
 * Ölçülen (12 Eyl 2026): 5 Eyl ölçümü "klavye ipucu YOK değil, YANLIŞ" demişti — `type="number"`
 * Türkçe yazımı (1.234,56) kabul etmez ve fare tekerleği değeri oynatır. Transactions/Accounts/
 * IncomeDebt/RedLines zaten text+decimal'di; dört para girdisi (bekleyen aksiyon düzenleme,
 * istek listesi, hedef tutarı, fırsat maliyeti) hâlâ number'dı ve ikisi `Number()` ile ayrıştırıyordu.
 *
 * Kilitlenen: `value={...amount...}` taşıyan hiçbir girdi `type="number"` değil; her para girdisi
 * `inputMode="decimal"`; gün/vade/oran gibi tam sayı girdileri number kalabilir.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const KOK = join(__dirname);
function jsx(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const y = join(dir, ad);
    if (statSync(y).isDirectory()) jsx(y, out);
    else if (ad.endsWith('.jsx') && !ad.includes('.test.')) out.push(y);
  }
  return out;
}

describe('UX-016 — para girdileri', () => {
  it('tutar taşıyan hiçbir <input> type="number" değil; hepsi inputMode="decimal"', () => {
    const ihlal = [];
    let para = 0;
    for (const f of jsx(KOK)) {
      const src = readFileSync(f, 'utf-8');
      for (const m of src.matchAll(/<input\b[^>]*>/gs)) {
        const tag = m[0];
        if (!/value=\{[^}]*(amount|target_amount|balance|price|tutar)/i.test(tag)) continue;
        if (/type="(checkbox|hidden)"/.test(tag)) continue;
        para += 1;
        const rel = f.split('src')[1];
        if (/type="number"/.test(tag)) ihlal.push(`${rel}: number`);
        else if (!/inputMode="decimal"/.test(tag)) ihlal.push(`${rel}: inputMode yok — ${tag.slice(0, 60)}`);
      }
    }
    expect(para, 'kapsam tabanı (L45)').toBeGreaterThanOrEqual(6);
    expect(ihlal, ihlal.join('\n')).toEqual([]);
  });
});
