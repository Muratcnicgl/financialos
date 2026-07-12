/**
 * api.js saf yardımcı fonksiyonları — para/yüzde/tarih/işaret formatlama.
 * Frontend'in ilk test kilidi (kalite serüveni TEST kategorisi). Bu fonksiyonlar
 * her panelde kullanılıyor ama test edilmemişti. formatDate saat-dilimi sağlamlığı
 * (date-only string bir gün kaymamalı) özellikle PROJE.md'nin uyardığı bug sınıfı.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import {
  formatTL, formatTLSuffix, formatPercent, formatDate, signClass,
  todayLocalISO, currentYearMonthLocal, parseTRNumber,
} from './api.js';

describe('parseTRNumber (W3-001)', () => {
  it('TR binlik + ondalık: "1.234,56" -> 1234.56 (eski bug: 1.234)', () => {
    expect(parseTRNumber('1.234,56')).toBe(1234.56);
    expect(parseTRNumber('12.345.678,90')).toBe(12345678.9);
  });
  it('TR yalnız ondalık virgül', () => {
    expect(parseTRNumber('1234,56')).toBe(1234.56);
    expect(parseTRNumber('-99,50')).toBe(-99.5);
    expect(parseTRNumber('0,01')).toBe(0.01);
  });
  it('TR yalnız nokta: 3-hane grup binlik, aksi ondalık', () => {
    expect(parseTRNumber('1.234')).toBe(1234);      // binlik
    expect(parseTRNumber('1.234.567')).toBe(1234567); // binlik
    expect(parseTRNumber('1.5')).toBe(1.5);          // ondalık
    expect(parseTRNumber('1.23')).toBe(1.23);        // ondalık
    expect(parseTRNumber('1.2345')).toBe(1.2345);    // ondalık
  });
  it('US formatı da tolere edilir', () => {
    expect(parseTRNumber('1,234.56')).toBe(1234.56);
    expect(parseTRNumber('1,234,567')).toBe(1234567);
    expect(parseTRNumber('1234.56')).toBe(1234.56);
  });
  it('TL sembolü, boşluk, sayısal geçiş', () => {
    expect(parseTRNumber('₺ 1.234,56')).toBe(1234.56);
    expect(parseTRNumber('  850  ')).toBe(850);
    expect(parseTRNumber(1234.56)).toBe(1234.56);
    expect(parseTRNumber('850')).toBe(850);
  });
  it('geçersiz -> NaN', () => {
    expect(parseTRNumber('')).toBeNaN();
    expect(parseTRNumber('abc')).toBeNaN();
    expect(parseTRNumber(null)).toBeNaN();
    expect(parseTRNumber(undefined)).toBeNaN();
    expect(parseTRNumber('-')).toBeNaN();
    expect(parseTRNumber(Infinity)).toBeNaN();
  });
});

describe('formatTL', () => {
  it('TR formatı: nokta binlik, virgül ondalık', () => {
    expect(formatTL(1234.56)).toBe('1.234,56');
    expect(formatTL(0)).toBe('0,00');
    expect(formatTL(-99.5)).toBe('-99,50');
  });
  it('compact modda ondalıksız yuvarlar', () => {
    expect(formatTL(1234.56, { compact: true })).toBe('1.235');
  });
  it('geçersiz değerde tire döner', () => {
    expect(formatTL(null)).toBe('—');
    expect(formatTL(undefined)).toBe('—');
    expect(formatTL(NaN)).toBe('—');
  });
});

describe('formatTLSuffix', () => {
  it('TL soneki ekler', () => {
    expect(formatTLSuffix(1234.56)).toBe('1.234,56 TL');
  });
  it('geçersizde tire (sonek yok)', () => {
    expect(formatTLSuffix(null)).toBe('—');
  });
});

describe('formatPercent', () => {
  it('pozitifte + işareti', () => {
    expect(formatPercent(36.3)).toBe('+%36,30');
  });
  it('negatifte + yok', () => {
    expect(formatPercent(-5)).toBe('%-5,00');
  });
  it('showSign=false ile + bastırılır', () => {
    expect(formatPercent(36.3, { showSign: false })).toBe('%36,30');
  });
  it('geçersizde tire', () => {
    expect(formatPercent(null)).toBe('—');
  });
});

describe('formatDate — saat-dilimi sağlam', () => {
  it('date-only string bir gün KAYMAZ (TZ bağımsız)', () => {
    // UTC-batı TZ'lerde 'new Date("2026-05-11")' 10 Mayıs gösterirdi; local parse ile 11 kalır.
    expect(formatDate('2026-05-11')).toBe('11 May');
    expect(formatDate('2026-01-01')).toBe('1 Oca');
    expect(formatDate('2026-12-31')).toBe('31 Ara');
  });
  it('withYear ile yıl ekler', () => {
    expect(formatDate('2026-05-11', { withYear: true })).toBe('11 May 2026');
  });
  it('boş/null → tire', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatDate('')).toBe('—');
  });
});

describe('signClass', () => {
  it('pozitif → positive class', () => {
    expect(signClass(5)).toContain('positive');
  });
  it('negatif → negative class', () => {
    expect(signClass(-5)).toContain('negative');
  });
  it('sıfır/geçersiz → nötr zinc', () => {
    expect(signClass(0)).toContain('zinc');
    expect(signClass(null)).toContain('zinc');
    expect(signClass(NaN)).toContain('zinc');
  });
});

describe('todayLocalISO / currentYearMonthLocal — gece vardiyası TZ güvenliği', () => {
  const origTZ = process.env.TZ;
  afterEach(() => { vi.useRealTimers(); process.env.TZ = origTZ; });

  it('Türkiye gece 01:30 (UTC 22:30 önceki gün) → LOCAL bugünü döner, geri KAYMAZ', () => {
    process.env.TZ = 'Europe/Istanbul';
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-11T22:30:00Z'));  // 01:30 May 12 Istanbul
    expect(todayLocalISO()).toBe('2026-05-12');
    // Eski (buggy) UTC yaklaşımı yanlış günü verirdi — regresyon kanıtı:
    expect(new Date().toISOString().slice(0, 10)).toBe('2026-05-11');
  });

  it('ay sınırında currentYearMonthLocal LOCAL ayı döner', () => {
    process.env.TZ = 'Europe/Istanbul';
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-31T22:30:00Z'));  // 01:30 Jun 1 Istanbul
    expect(currentYearMonthLocal()).toBe('2026-06');
  });
});
