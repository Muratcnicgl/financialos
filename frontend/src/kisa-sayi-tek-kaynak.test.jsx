/**
 * DVIZ-014 KAPISI (BUG #454) — GRAFİK KISA SAYI BİÇİMİ TEK KAYNAK.
 *
 * Ölçülen (13 Eyl 2026): aynı ekranda üç kısaltma: Reports çubuk `shortTL` ("12,3K"),
 * Reports Y ekseni `fmtYAxis` ("12K"), BalanceTrend ekseni `formatSayi(compact)` ("12.300").
 * Tek kaynak `lib/money.js::kisaSayi` — yerel Intl compact (tr-TR: B/Mn).
 *
 * Kilitlenen: `kisaSayi` çıktıları; Reports/BalanceTrend yerel kısaltıcı tanımlamaz ve
 * eksen/etiket biçimlendiricisi olarak `kisaSayi` kullanır.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { kisaSayi } from './lib/money.js';

const KOK = join(__dirname);

describe('DVIZ-014 — kısa sayı', () => {
  it('kisaSayi Türkçe compact gösterim verir', () => {
    const d = (s) => s.replace(/ /g, ' ');   // Intl bölünmez boşluk basar
    expect(d(kisaSayi(12300))).toBe('12,3 B');
    expect(kisaSayi(950)).toBe('950');
    expect(d(kisaSayi(1250000))).toBe('1,3 Mn');
    expect(d(kisaSayi(-4500))).toBe('-4,5 B');
    expect(kisaSayi(null)).toBe('—');
  });

  it('grafikler yerel kısaltıcı tanımlamaz, kisaSayi kullanır', () => {
    const rep = readFileSync(join(KOK, 'panels', 'Reports.jsx'), 'utf-8');
    expect(rep).not.toMatch(/function (shortTL|fmtYAxis)\b/);
    expect(rep).toMatch(/formatter=\{kisaSayi\}/);
    expect(rep).toMatch(/tickFormatter=\{kisaSayi\}/);
    const bt = readFileSync(join(KOK, 'components', 'BalanceTrend.jsx'), 'utf-8');
    expect(bt).toMatch(/tickFormatter=\{kisaSayi\}/);
  });
});
