/**
 * A11Y-010 KAPISI — PANEL YÜKLENİRKEN EKRAN OKUYUCU SESSİZ KALIYORDU.
 *
 * Ölçülen (11 Eyl 2026): dört panel (Accounts, IncomeDebt, RedLines, Transactions) aynı
 * yükleme bloğunu kopyalıyordu — ortada dönen bir ikon, ne `role="status"` ne `aria-busy`
 * ne de okunabilir bir metin. Gören kullanıcı "yükleniyor" anlar; ekran okuyucu için
 * panel BOŞ görünür (WCAG 4.1.3).
 *
 * Kilitlenen: `w-8 h-8 animate-spin` taşıyan her panel-düzeyi yükleme bloğunun
 * sarmalayıcısı `role="status"` taşır ve okunabilir bir metin içerir. Kaynaktan türetilir.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

function jsxDosyalari(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) jsxDosyalari(yol, out);
    else if (ad.endsWith('.jsx') && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

function sessizYuklemeBloklari() {
  const bulgular = [];
  for (const f of jsxDosyalari(join(__dirname))) {
    const satirlar = readFileSync(f, 'utf-8').split('\n');
    satirlar.forEach((s, i) => {
      if (!s.includes('w-8 h-8 animate-spin')) return;
      const sarmalayici = satirlar[i - 1] || '';
      const sonraki = satirlar[i + 1] || '';
      if (!sarmalayici.includes('role="status"') || !sonraki.includes('sr-only')) {
        bulgular.push(`${f.split('src')[1]}:${i + 1}`);
      }
    });
  }
  return bulgular;
}

describe('A11Y-010 — panel yükleme durumu duyurulur', () => {
  it('panel-düzeyi yükleme bloklarının hepsi role="status" + okunabilir metin taşır', () => {
    const b = sessizYuklemeBloklari();
    expect(b, `sessiz yükleme bloğu:\n${b.join('\n')}`).toEqual([]);
  });

  it('kapı en az dört bloğu gerçekten tarıyor (boş kümede sahte yeşil olmasın)', () => {
    let sayac = 0;
    for (const f of jsxDosyalari(join(__dirname))) {
      sayac += (readFileSync(f, 'utf-8').match(/w-8 h-8 animate-spin/g) || []).length;
    }
    expect(sayac).toBeGreaterThanOrEqual(4);
  });
});
