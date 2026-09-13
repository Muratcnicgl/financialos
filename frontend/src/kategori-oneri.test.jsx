/**
 * UX-009 KAPISI (BUG #468) — HIZLI GİRİŞ KATEGORİ ÖNERİR.
 * Kilitlenen: en sık gider kategorileri (sistem kategorileri hariç, eşitlikte alfabetik), metin
 * yalnız tutarken çipler görünür, çip tıklayınca metin tamamlanır, kategori yazılınca çipler
 * kaybolur.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { enSikKategoriler, yalnizTutar } from './lib/kategoriOneri.js';

const TX = [
  { transaction_type: 'expense', category: 'market' }, { transaction_type: 'expense', category: 'market' },
  { transaction_type: 'expense', category: 'ulasim' }, { transaction_type: 'expense', category: 'borc_odeme' },
  { transaction_type: 'income', category: 'maas' }, { transaction_type: 'expense', category: 'kahve' },
  { transaction_type: 'expense', category: '' },
];

describe('UX-009 — kategori önerisi', () => {
  it('sıklık + alfabetik; sistem/boş hariç; yalnız-tutar tespiti', () => {
    expect(enSikKategoriler(TX)).toEqual(['market', 'kahve', 'ulasim']);
    expect(enSikKategoriler(TX, 1)).toEqual(['market']);
    expect(enSikKategoriler([])).toEqual([]);
    expect(yalnizTutar('320')).toBe(true);
    expect(yalnizTutar('1.250,50 ')).toBe(true);
    expect(yalnizTutar('320 market')).toBe(false);
    expect(yalnizTutar('')).toBe(false);
  });

  it('çipler yalnız tutarken görünür ve metni tamamlar', async () => {
    vi.resetModules();
    const { default: Transactions } = await import('./panels/Transactions.jsx');
    const bos = { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => [], text: async () => '[]' };
    global.fetch = vi.fn(async (url) => {
      const yol = new URL(url, 'http://localhost').pathname;
      if (yol === '/api/transactions') return { ...bos, json: async () => TX.map((t, i) => ({ id: i + 1, amount: 10, transaction_date: '2026-09-10', account_id: 1, ...t })) };
      if (yol === '/api/accounts') return { ...bos, json: async () => [{ id: 1, name: 'Kasa', account_type: 'cash', balance: 100 }] };
      if (yol === '/api/cockpit') return { ...bos, json: async () => ({ bugun_kalan: 1000, daily_limit: 1000, bugun_harcanan: 0 }) };
      return bos;
    });
    const { ToastProvider } = await import('./components/Toast.jsx');
    render(<ToastProvider><Transactions /></ToastProvider>);
    const girdi = await screen.findByPlaceholderText(/Hızlı giriş/);
    expect(screen.queryByTestId('kategori-onerileri')).toBeNull();
    fireEvent.change(girdi, { target: { value: '320' } });
    const grup = await screen.findByTestId('kategori-onerileri');
    expect(grup.textContent).toMatch(/market/);
    fireEvent.click(screen.getByRole('button', { name: 'market' }));
    await waitFor(() => expect(girdi.value).toBe('320 market'));
    expect(screen.queryByTestId('kategori-onerileri')).toBeNull();
  });
});
