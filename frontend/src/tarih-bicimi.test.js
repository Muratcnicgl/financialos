/**
 * A11Y-015 KAPISI (BUG #398) — TARİH BİÇİMİ `Intl` İLE, ELLE DİZİYLE DEĞİL.
 *
 * Ölçülen (11 Eyl 2026): `formatTL` Intl kullanıyordu, `formatDate` 12 elemanlı elle bir ay
 * dizisiyle biçimliyordu — yerel ayarı kod taşıyordu. `Intl.DateTimeFormat('tr-TR')` aynı
 * kısaltmaları üretir (12 ay birebir ölçüldü). Kilitlenen: çıktı sözleşmesi (12 ay, yıl
 * varyantı, tarih-only string'in saat diliminden bağımsızlığı, boş/bozuk girdi) ve kaynakta
 * elle ay dizisinin OLMAMASI.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { formatDate } from './api.js';

const AYLAR = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];

describe('formatDate', () => {
  it('12 ayın kısaltması Türkçe ve gün başta', () => {
    AYLAR.forEach((ay, i) => {
      const mm = String(i + 1).padStart(2, '0');
      expect(formatDate(`2026-${mm}-05`)).toBe(`5 ${ay}`);
    });
  });
  it('yıl varyantı ve datetime girdisi', () => {
    expect(formatDate('2026-08-03', { withYear: true })).toBe('3 Ağu 2026');
    expect(formatDate('2026-05-11T10:00:00+00:00')).toMatch(/^11 May$/);
  });
  it('boş ve bozuk girdi', () => {
    expect(formatDate('')).toBe('—');
    expect(formatDate(null)).toBe('—');
    expect(formatDate('bozuk')).toBe('bozuk');
  });
  it('kaynakta elle ay dizisi yok, Intl var', () => {
    const src = readFileSync(join(__dirname, 'api.js'), 'utf-8');
    expect(src).not.toMatch(/\['Oca',\s*'Şub'/);
    expect(src).toMatch(/Intl\.DateTimeFormat\('tr-TR'/);
  });
});
