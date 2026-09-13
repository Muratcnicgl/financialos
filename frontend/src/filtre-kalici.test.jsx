/**
 * UX-037 KAPISI (BUG #462) — FİLTRE TERCİHLERİ OTURUMLAR ARASI HATIRLANIR.
 *
 * Ölçülen (13 Eyl 2026): Transactions (tür/kategori/hesap), IncomeDebt (yön/ödeme), RedLines
 * (tip/aktif) filtreleri her açılışta varsayılana dönüyordu. Tarih aralığı BİLEREK hatırlanmaz
 * ("bugüne göre" anlam taşır; dünkü aralık bugün yanlış olur).
 *
 * Kilitlenen: `useKaliciDurum` yazar/okur, bozuk kayıtta varsayılana düşer, depolama kapalıyken
 * fırlatmaz; üç panel yedi filtreyi bu kancayla tutar; tarih alanları düz useState kalır.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { useKaliciDurum, kaliciOku } from './lib/kaliciDurum.js';

beforeEach(() => localStorage.clear());

describe('UX-037 — kalıcı filtre', () => {
  it('yazar, yeniden okur; bozuk kayıtta varsayılan; depolama hatası fırlatmaz', () => {
    const { result } = renderHook(() => useKaliciDurum('deneme', 'all'));
    expect(result.current[0]).toBe('all');
    act(() => result.current[1]('income'));
    expect(JSON.parse(localStorage.getItem('fos_filtre_deneme'))).toBe('income');
    const { result: r2 } = renderHook(() => useKaliciDurum('deneme', 'all'));
    expect(r2.current[0]).toBe('income');
    localStorage.setItem('fos_filtre_bozuk', '{not json');
    expect(kaliciOku('bozuk', 'x')).toBe('x');
    const orijinal = Storage.prototype.getItem;
    Storage.prototype.getItem = () => { throw new Error('kapalı'); };
    try { expect(kaliciOku('deneme', 'y')).toBe('y'); } finally { Storage.prototype.getItem = orijinal; }
  });

  it('üç panel filtreleri kancayla tutar; tarih alanları düz useState', () => {
    const say = (dosya, re) => (readFileSync(join(__dirname, 'panels', dosya), 'utf-8').match(re) || []).length;
    expect(say('Transactions.jsx', /useKaliciDurum\('islem-/g)).toBe(3);
    expect(say('IncomeDebt.jsx', /useKaliciDurum\('gelirborc-/g)).toBe(2);
    expect(say('RedLines.jsx', /useKaliciDurum\('kirmizi-/g)).toBe(2);
    const tx = readFileSync(join(__dirname, 'panels', 'Transactions.jsx'), 'utf-8');
    expect(tx).toMatch(/const \[filterDateFrom, setFilterDateFrom\] = useState\(''\)/);
  });
});
