/**
 * UX-025 KAPISI (BUG #463) — EKSTRA ÖDEME KAYDIRICISI REEL BÜTÇEYE ÖLÇEKLİ.
 *
 * Ölçülen (13 Eyl 2026): tavan sabit 5.000; bütçesi 20.000 olan da 800 olan da aynı
 * kaydırıcıyı görüyordu. Tavan = reel bütçenin %125'i (500'e yuvarlı, ≥ 1.000); bütçe
 * bilinmiyor/negatifse 5.000 (belgeli eski davranış). Referans işareti "ayırabileceğin ~X".
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { sliderTavani, referansYuzde, VARSAYILAN_TAVAN } from './lib/sliderTavani.js';

describe('UX-025 — kaydırıcı tavanı', () => {
  it('tavan bütçeden; bilinmiyorsa 5.000; taban 1.000; referans yüzdesi', () => {
    expect(sliderTavani(20000)).toBe(25000);
    expect(sliderTavani(800)).toBe(1000);
    expect(sliderTavani(4100)).toBe(5500);
    expect(sliderTavani(null)).toBe(VARSAYILAN_TAVAN);
    expect(sliderTavani(-300)).toBe(VARSAYILAN_TAVAN);
    expect(referansYuzde(20000, 25000)).toBe(80);
    expect(referansYuzde(null, 5000)).toBeNull();
  });

  it('DebtStrategy kaydırıcıyı tavana bağlar ve bütçeyi okur (kaynak bağı)', () => {
    const src = readFileSync(join(__dirname, 'panels', 'DebtStrategy.jsx'), 'utf-8');
    expect(src).toMatch(/max=\{tavan\}/);
    expect(src).not.toMatch(/max="5000"/);
    expect(src).toMatch(/cockpitApi\.get\(\)/);
    expect(src).toMatch(/ayırabileceğin ~/);
  });
});
