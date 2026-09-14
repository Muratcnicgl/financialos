/**
 * UX-024 (BUG #479): "Bu planı benimse" — analiz taahhüde dönüşür.
 *
 * Ölçüm (14 Eyl 2026): Borç Stratejisi iki planı karşılaştırıyor, hiçbirini hedefe
 * bağlamıyordu; debt_freedom hedefinin tahmini bitişi her zaman Snowball/0 ile hesaplanıyordu.
 * Kilitlenen: iki kartta da buton; mevcut borç hedefi YOKSA yaratılır (tutar = toplam borç,
 * tarih = planın bitişi, plan = strateji + slider ekstra), VARSA plan ona yazılır; benimsenen
 * kart "✓" gösterir; hata yolu toast'la görünür.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const STRATEJI = (ad, ay, tarih) => ({
  strategy: ad, order: [1, 2], months_to_freedom: ay, total_interest_paid: 5000, total_paid: 40000,
  payoff_date: tarih, debt_payoff_months: {}, kalan_seri: [],
});
const VERI = {
  debts: [
    { account_id: 1, name: 'Kart', account_type: 'credit_card', balance: 30000, interest_rate_monthly: 4, min_payment: 900 },
    { account_id: 2, name: 'Kredi', account_type: 'loan', balance: 120000, interest_rate_monthly: 3.5, min_payment: 6000 },
  ],
  snowball: STRATEJI('snowball', 20, '2028-05-01'),
  avalanche: STRATEJI('avalanche', 18, '2028-03-01'),
  warnings: [],
  comparison: { interest_saved_with_avalanche: 1200, months_difference: 2, recommendation_note: 'Çığ daha ucuz.' },
};

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return {
    ...gercek,
    debtStrategyApi: { compare: vi.fn(), consolidation: vi.fn(), opportunityCost: vi.fn() },
    cockpitApi: { get: vi.fn().mockResolvedValue({ reel_butce: 15000 }) },
    goalsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn() },
  };
});

import DebtStrategy from './panels/DebtStrategy.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { debtStrategyApi, goalsApi } from './api.js';
import { planEtiketi } from './lib/borcPlani.js';

async function kur(mevcutHedef = null) {
  debtStrategyApi.compare.mockResolvedValue(VERI);
  goalsApi.list.mockResolvedValue(mevcutHedef ? [mevcutHedef] : []);
  render(<ToastProvider><DebtStrategy /></ToastProvider>);
  await screen.findAllByRole('button', { name: /Bu planı benimse|Benimsenen plan/ });
}

beforeEach(() => vi.clearAllMocks());

describe('UX-024 — planı benimse', () => {
  it('iki kartta da buton var; hedef yokken yaratır (tutar = toplam borç, tarih = bitiş, plan = strateji+ekstra)', async () => {
    await kur();
    const butonlar = screen.getAllByRole('button', { name: 'Bu planı benimse' });
    expect(butonlar).toHaveLength(2);
    goalsApi.create.mockResolvedValue({ id: 7, plan: { strateji: 'avalanche', aylik_ekstra: 0 } });
    fireEvent.click(butonlar[1]);   // ikinci kart: Avalanche
    await waitFor(() => expect(goalsApi.create).toHaveBeenCalledTimes(1));
    const govde = goalsApi.create.mock.calls[0][0];
    expect(govde.goal_type).toBe('debt_freedom');
    expect(govde.target_amount).toBe(150000);
    expect(govde.target_date).toBe('2028-03-01');
    expect(govde.plan).toEqual({ strateji: 'avalanche', aylik_ekstra: 0 });
    expect(goalsApi.update).not.toHaveBeenCalled();
    expect(await screen.findByRole('button', { name: 'Benimsenen plan ✓' })).toBeDisabled();
    expect(screen.getByText(/Plan benimsendi/)).toBeInTheDocument();
  });

  it('mevcut borç hedefi varsa plan ona yazılır, ikinci hedef üretilmez', async () => {
    await kur({ id: 3, goal_type: 'debt_freedom', plan: { strateji: 'snowball', aylik_ekstra: 0 } });
    // Snowball/0 zaten benimsenmiş görünür
    expect(screen.getByRole('button', { name: 'Benimsenen plan ✓' })).toBeInTheDocument();
    goalsApi.update.mockResolvedValue({ id: 3, plan: { strateji: 'avalanche', aylik_ekstra: 0 } });
    fireEvent.click(screen.getByRole('button', { name: 'Bu planı benimse' }));
    await waitFor(() => expect(goalsApi.update).toHaveBeenCalledWith(3, { plan: { strateji: 'avalanche', aylik_ekstra: 0 }, target_date: '2028-03-01' }));
    expect(goalsApi.create).not.toHaveBeenCalled();
  });

  it('sunucu reddederse hata görünür, durum değişmez', async () => {
    await kur();
    goalsApi.create.mockRejectedValue(new Error('kota'));
    fireEvent.click(screen.getAllByRole('button', { name: 'Bu planı benimse' })[0]);
    expect(await screen.findByText(/Plan benimsenemedi/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Bu planı benimse' })).toHaveLength(2);
  });

  it('plan etiketi: strateji adı + ekstra (0 ise yalnız ad)', () => {
    expect(planEtiketi({ strateji: 'avalanche', aylik_ekstra: 1500 })).toMatch(/^Çığ \+ .*1\.500.*\/ay$/);
    expect(planEtiketi({ strateji: 'snowball', aylik_ekstra: 0 })).toBe('Kartopu');
    expect(planEtiketi(null)).toBe('');
  });
});
