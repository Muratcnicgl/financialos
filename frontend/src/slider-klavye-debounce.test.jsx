/**
 * FE-018 KAPISI (BUG #403) — SLIDER KLAVYE TAAHHÜDÜ DEBOUNCE'LU.
 *
 * Ölçülen (11 Eyl 2026): `onKeyUp={handleExtraCommit}` her ok tuşunda bir istek atıyordu;
 * tuş basılı tutulunca saniyede onlarca `compare` isteği. Fare/dokunma bırakışta tek istek
 * atıyordu; klavye kullanıcısı ceza yiyordu. Kilitlenen: 5 ok tuşu → 300 ms sonra TEK istek;
 * fare bırakışı hemen istek.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return {
    ...gercek,
    debtStrategyApi: {
      compare: vi.fn().mockResolvedValue({
        debts: [{ account_id: 1, name: 'Kart', account_type: 'credit_card', balance: 1000,
                  interest_rate_monthly: 0.03, min_payment: 200 }],
        snowball: null, avalanche: null, warnings: [],
        comparison: { interest_saved_with_avalanche: 0, months_difference: 0, recommendation_note: '' },
      }),
      consolidation: vi.fn(), opportunityCost: vi.fn(),
    },
  };
});

import DebtStrategy from './panels/DebtStrategy.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { debtStrategyApi } from './api.js';

async function kur() {
  render(<ToastProvider><DebtStrategy /></ToastProvider>);
  // ilk yükleme isteği
  await screen.findByRole('slider');
  debtStrategyApi.compare.mockClear();
  return screen.getByRole('slider');
}

describe('FE-018 — ekstra ödeme slider taahhüdü', () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));

  it('5 ok tuşu → 300 ms sonra tek istek', async () => {
    const slider = await kur();
    for (let i = 0; i < 5; i += 1) {
      fireEvent.change(slider, { target: { value: String(100 * (i + 1)) } });
      fireEvent.keyUp(slider, { key: 'ArrowRight' });
    }
    expect(debtStrategyApi.compare).not.toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(350); });
    expect(debtStrategyApi.compare).toHaveBeenCalledTimes(1);
    expect(debtStrategyApi.compare).toHaveBeenLastCalledWith({ extraMonthly: 500 });
  });

  it('fare bırakışı bekletmez', async () => {
    const slider = await kur();
    fireEvent.change(slider, { target: { value: '700' } });
    fireEvent.mouseUp(slider);
    expect(debtStrategyApi.compare).toHaveBeenCalledTimes(1);
  });
});
