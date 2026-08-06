/**
 * BUG #256 (H4) — `lib/money.js` tek kaynağının davranış kilidi.
 *
 * Bu dosya, refactor öncesi DÖRT ayrı biçimlendiricinin ürettiği tutarsızlıkları
 * kilitler. Refactor'dan önce aynı ekranda şunlar oluyordu:
 *   - `api.js formatTL(null)`            -> "—"
 *   - `DebtStrategy.jsx TL(null)`        -> "₺0"     (null'ı sıfır para sandı)
 *   - `formatTL` 2 ondalık, `TL()` 0 ondalık
 *   - `HorizonsModal`/`PremortemModal` kendi `toLocaleString`'u + elle ' TL'
 * Artık hepsi tek fonksiyondan geçer; aşağıdaki testler o sözleşmedir.
 */
import { describe, it, expect } from 'vitest';
import { formatSayi, formatPara, paraEtiketi, formatParaSimge, PARA_BIRIMI } from './lib/money.js';
import { formatTL, formatTLSuffix } from './api.js';

describe('lib/money.js — tek kaynak', () => {
  it('sayıyı Türkçe biçimde yazar (nokta binlik, virgül ondalık)', () => {
    expect(formatSayi(1234.56)).toBe('1.234,56');
    expect(formatSayi(0)).toBe('0,00');
    expect(formatSayi(-42100.5)).toBe('-42.100,50');
  });

  it('para etiketini TEK kaynaktan ekler', () => {
    expect(formatPara(1234.56)).toBe('1.234,56 TL');
    expect(paraEtiketi()).toBe(PARA_BIRIMI.etiket);
  });

  it('boş/geçersiz değerde em-dash döner — "0 TL" YAZMAZ', () => {
    // Eski `DebtStrategy.TL(null)` "₺0" diyordu: veri yokken sıfır para göstermek YALANDIR.
    for (const bos of [null, undefined, NaN, 'abc']) {
      expect(formatSayi(bos)).toBe('—');
      expect(formatPara(bos)).toBe('—');
    }
  });

  it('compact ve ondalık seçenekleri aynı fonksiyondan gelir', () => {
    expect(formatSayi(1234.56, { compact: true })).toBe('1.235');
    expect(formatPara(1234.56, { ondalik: 0 })).toBe('1.235 TL');
  });

  it('sembol biçimi de tek kaynaktan gelir', () => {
    expect(formatParaSimge(1234.56)).toBe('₺1.235');
  });
});

describe('api.js geriye uyum', () => {
  it('formatTL / formatTLSuffix aynı gövdeye devreder', () => {
    expect(formatTL(1234.56)).toBe(formatSayi(1234.56));
    expect(formatTLSuffix(1234.56)).toBe(formatPara(1234.56));
    expect(formatTLSuffix(1234.56)).toBe('1.234,56 TL');
  });

  it('null davranışı iki isimde de aynı', () => {
    expect(formatTL(null)).toBe('—');
    expect(formatTLSuffix(null)).toBe('—');
  });
});

describe('sözleşme: backend ile hizalı', () => {
  it('para birimi kodu ve etiketi backend money_format ile aynı olmalı', () => {
    // Backend: app/money_format.PARA_BIRIMLERI['TRY'] = (kod TRY, etiket TL, simge ₺)
    expect(PARA_BIRIMI.kod).toBe('TRY');
    expect(PARA_BIRIMI.etiket).toBe('TL');
    expect(PARA_BIRIMI.simge).toBe('₺');
  });
});
