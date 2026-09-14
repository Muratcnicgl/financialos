/**
 * UX-026 KAPISI (BUG #472) — DÜŞÜK RİSKLİ BEKLEYENLER TOPLU ONAYLANIR.
 * Kilitlenen: düğme yalnız ≥2 düşük riskli aksiyonda; sell_investment/update_account_balance/
 * pay_credit_card kümede değil ve toplu onaya girmez; sırayla onaylar, her biri onResolved;
 * ilk hatada durur ve hata satırda kalır.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return { ...gercek, actionsApi: { approve: vi.fn(), reject: vi.fn(), edit: vi.fn(), pending: vi.fn(), gecmis: vi.fn() } };
});
import PendingActions, { TOPLU_ONAY_TIPLERI } from './components/PendingActions.jsx';
import { actionsApi } from './api.js';

const A = (id, tip) => ({ id, action_type: tip, summary: `a${id}`, payload: JSON.stringify({ amount: 1, account_id: 1 }) });

describe('UX-026 — toplu onay', () => {
  it('riskli tipler kümede değil', () => {
    for (const t of ['sell_investment', 'update_account_balance', 'pay_credit_card']) expect(TOPLU_ONAY_TIPLERI.has(t)).toBe(false);
    expect(TOPLU_ONAY_TIPLERI.has('add_transaction')).toBe(true);
  });

  it('tek düşük riskli aksiyonda düğme yok; ikide var ve sırayla onaylar, riskliyi atlar', async () => {
    const cozuldu = vi.fn();
    const { unmount } = render(<PendingActions actions={[A(1, 'add_transaction'), A(2, 'sell_investment')]} onResolved={cozuldu} accounts={[]} />);
    expect(screen.queryByTestId('toplu-onay')).toBeNull();
    unmount();
    actionsApi.approve.mockResolvedValue({ ok: true });
    render(<PendingActions actions={[A(1, 'add_transaction'), A(2, 'sell_investment'), A(3, 'mark_debt_paid')]} onResolved={cozuldu} accounts={[]} />);
    fireEvent.click(screen.getByRole('button', { name: /Hepsini onayla \(2\)/ }));
    await waitFor(() => expect(actionsApi.approve).toHaveBeenCalledTimes(2));
    expect(actionsApi.approve.mock.calls.map((c) => c[0])).toEqual([1, 3]);
    expect(cozuldu).toHaveBeenCalledTimes(2);
  });

  it('ilk hatada durur, hata satırda kalır', async () => {
    actionsApi.approve.mockReset();
    actionsApi.approve.mockRejectedValueOnce(new Error('limit aşıldı')).mockResolvedValue({ ok: true });
    render(<PendingActions actions={[A(1, 'add_transaction'), A(3, 'add_transaction')]} onResolved={vi.fn()} accounts={[]} />);
    fireEvent.click(screen.getByRole('button', { name: /Hepsini onayla/ }));
    await waitFor(() => expect(screen.getByText(/limit aşıldı/)).toBeInTheDocument());
    expect(actionsApi.approve).toHaveBeenCalledTimes(1);
  });
});
