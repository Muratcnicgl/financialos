/**
 * UX-032 KAPISI (BUG #470) — BAYAT FİYAT SATIRINDA MODALSIZ FİYAT GİRİŞİ.
 * Kilitlenen: geçersiz sayı gönderilmez (inline hata, aria-invalid); geçerli fiyat aynı uca
 * (`fund-price/update`) gider ve ebeveyn yenilenir; kokpitte yalnız bayat satırda görünür.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return { ...gercek, fundPriceApi: { update: vi.fn().mockResolvedValue({}) } };
});
import SatirIciFiyat from './components/SatirIciFiyat.jsx';
import { fundPriceApi } from './api.js';

describe('UX-032 — satır içi fiyat', () => {
  it('geçersiz sayı gönderilmez; geçerli fiyat uca gider ve yeniler', async () => {
    const yenile = vi.fn();
    render(<SatirIciFiyat accountId={7} name="TLY" onUpdated={yenile} />);
    const girdi = screen.getByLabelText('TLY yeni fiyat');
    fireEvent.change(girdi, { target: { value: 'abc' } });
    fireEvent.submit(girdi.closest('form'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Geçerli bir fiyat gir');
    expect(girdi).toHaveAttribute('aria-invalid', 'true');
    expect(fundPriceApi.update).not.toHaveBeenCalled();
    fireEvent.change(girdi, { target: { value: '5.223,81' } });
    fireEvent.submit(girdi.closest('form'));
    await waitFor(() => expect(fundPriceApi.update).toHaveBeenCalledWith(7, 5223.81));
    await waitFor(() => expect(yenile).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole('status')).toHaveTextContent('Güncellendi');
  });

  it('kokpitte yalnız bayat satırda (kaynak bağı)', () => {
    const src = readFileSync(join(__dirname, 'panels', 'Cockpit.jsx'), 'utf-8');
    expect(src).toMatch(/\{item\.is_stale && \(\s*<SatirIciFiyat accountId=\{item\.account_id\}/);
  });
});
