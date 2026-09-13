/**
 * UX-004 + UX-005 KAPISI (BUG #467) — BUGÜN KALAN CANLI; HIZLI GİRİŞTE AŞIM ONAYI.
 *
 * Ölçülen (13 Eyl 2026): günlük limit pasifti (bugünkü işlemler düşülmüyordu); hızlı giriş
 * limiti aşan tutarı sessizce yazıyordu. Kilitlenen: cümle (kalan / aşım → "yarınki limit
 * düşer"), aşım hesabı, tutar ayrıştırma; Cockpit çubuğu bağlı; hızlı girişte aşımda bir
 * adımlık onay, "Yine de ekle" ile devam, günde bir kez (localStorage).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { kalanCumlesi, asimMiktari, hizliTutar } from './lib/bugunKalan.js';
import { parseTRNumber } from './api.js';

describe('UX-004 — bugün kalan', () => {
  it('cümle ve hesaplar', () => {
    expect(kalanCumlesi(120, 620)).toMatch(/Bugün kalan 120 TL \/ 620 TL/);
    expect(kalanCumlesi(-80, 620)).toMatch(/80 TL aşıldı — yarınki limit o kadar düşer/);
    expect(kalanCumlesi(null, 620)).toBeNull();
    expect(asimMiktari(500, 120)).toBe(380);
    expect(asimMiktari(100, 120)).toBe(0);
    expect(asimMiktari(-5, 120)).toBe(0);
    expect(hizliTutar('320 borc', parseTRNumber)).toBe(320);
    expect(hizliTutar('1.250,50 kira', parseTRNumber)).toBe(1250.5);
    expect(hizliTutar('kira 300', parseTRNumber)).toBeNull();
    const src = readFileSync(join(__dirname, 'panels', 'Cockpit.jsx'), 'utf-8');
    expect(src).toMatch(/data-testid="bugun-kalan"/);
    expect(src).toMatch(/kalanCumlesi\(data\.bugun_kalan, data\.daily_limit\)/);
  });
});

describe('UX-005 — hızlı girişte aşım onayı', () => {
  it('aşımda bir adımlık onay; "Yine de ekle" gönderir; aynı gün ikinci kez sormaz', async () => {
    vi.resetModules();
    const { default: Transactions } = await import('./panels/Transactions.jsx');
    const gonder = vi.fn(async () => ({}));
    const bos = { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => [], text: async () => '[]' };
    global.fetch = vi.fn(async (url, opts = {}) => {
      const yol = new URL(url, 'http://localhost').pathname;
      if (yol === '/api/cockpit') return { ...bos, json: async () => ({ bugun_kalan: 120, daily_limit: 620, bugun_harcanan: 500 }) };
      if (yol === '/api/accounts') return { ...bos, json: async () => [{ id: 1, name: 'Kasa', account_type: 'cash', balance: 100 }] };
      if (yol === '/api/transactions' && opts.method === 'POST') { gonder(JSON.parse(opts.body)); return { ...bos, status: 201, json: async () => ({ id: 9 }) }; }
      return bos;
    });
    const { ToastProvider } = await import('./components/Toast.jsx');
    render(<ToastProvider><Transactions /></ToastProvider>);
    const girdi = await screen.findByPlaceholderText(/Hızlı giriş/);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/cockpit/), expect.anything()));
    fireEvent.change(girdi, { target: { value: '500 market' } });
    fireEvent.submit(girdi.closest('form'));
    const onay = await screen.findByTestId('asim-onayi');
    expect(onay).toHaveTextContent('380 TL aşıyor');
    expect(gonder).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Yine de ekle/ }));
    await waitFor(() => expect(gonder).toHaveBeenCalledTimes(1));
    // aynı gün ikinci aşım: sormaz
    fireEvent.change(girdi, { target: { value: '900 market' } });
    fireEvent.submit(girdi.closest('form'));
    await waitFor(() => expect(gonder).toHaveBeenCalledTimes(2));
    expect(screen.queryByTestId('asim-onayi')).toBeNull();
  });
});
