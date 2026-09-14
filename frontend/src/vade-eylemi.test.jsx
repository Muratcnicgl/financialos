/**
 * UX-013 (BUG #477): yaklaşan vade satırı tek tıkla eyleme dönüşür.
 *
 * Ölçüm (14 Eyl 2026): kokpitteki "Yaklaşan vadeler" pasif bir listeydi — borç için
 * "Ödedim", alacak için "Geldi", kart son ödemesi için "Koça sor" yoktu; kullanıcı Gelir &
 * Borç paneline gidip aynı kalemi arıyordu. Burada:
 *  - borç → Ödedim: PUT /debts/{kaynak_id} is_paid, kokpit tazelenir,
 *  - alacak → Geldi: aynı yol (tahsilat nakde geçer, BUG #241),
 *  - kart → Koça sor: hazır soru bırakılır, sekme koça geçer; Coach girdiyi hazır alır,
 *  - düzenli gelir/gider satırı buton TAŞIMAZ (öneri zaten trigger-due ile üretilir),
 *  - kimliksiz kalem (eski sunucu) eylem taşımaz.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const COCKPIT = {
  statu: 'Nakit akışın dengede.',
  nakit_kasa: 12000, kart_borcu: 3000, kredi_borcu: 0, yatirim_deger: 0, emanet_kasa: 0,
  beklenen_gelir: 20000, reel_butce: 15000, net_deger: 6000, net_deger_tam: 9000,
  alacaklar_toplami: 700, borclar_toplami: 500,
  today_target: 660, daily_limit: 620, days_remaining: 22, carried_forward: 0,
  butce_dokum: { nakit: 12000, beklenen_gelir: 20000, kart_borcu: 3000, bu_ayki_taksit: 0,
                 reel_butce: 15000, days_remaining: 22, daily_limit: 620, alacak_haric: 700 },
  sonraki_eylem: { tip: 'firsat', eylem: 'Kart borcunu kapat', gerekce: 'Faiz.' },
  alerts: [], gizli_uyari_sayisi: 0,
  accounts: [{ id: 1, name: 'Nakit Kasa', account_type: 'cash', bakiye: 12000 }],
  upcoming_reminders: [
    { type: 'card_payment', kaynak_id: 9, name: 'Kart son ödeme', account_name: 'Kart', amount: 3000, days_until: 3, card_risk: true },
    { type: 'debt', kaynak_id: 41, name: 'Ali borcu', amount: 500, days_until: 1, account_name: '' },
    { type: 'receivable', kaynak_id: 42, name: 'Veli alacağı', amount: 700, days_until: 5, account_name: '' },
    { type: 'expense', kaynak_id: 7, name: 'Kira', amount: 10000, days_until: 2, account_name: 'Nakit Kasa' },
    { type: 'debt', name: 'Eski sunucu borcu', amount: 50, days_until: 6, account_name: '' },
  ],
  upcoming_payments: [], upcoming_receivables: [],
  price_freshness: { stale_count: 0, items: [] },
};

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return {
    ...gercek,
    cockpitApi: { get: vi.fn() },
    actionsApi: { pending: vi.fn().mockResolvedValue([]), gecmis: vi.fn().mockResolvedValue([]) },
    incomesApi: { triggerDue: vi.fn().mockResolvedValue({ triggered: [], atlanan: [] }) },
    expensesApi: { triggerDue: vi.fn().mockResolvedValue({ triggered: [], atlanan: [] }) },
    cashflowApi: { getForecast: vi.fn().mockResolvedValue({ summary: null }) },
    fundPriceApi: { update: vi.fn() },
    debtsApi: { update: vi.fn() },
    reportsApi: {
      monthlySummary: vi.fn().mockRejectedValue(new Error('kapalı')),
      monthlySeries: vi.fn().mockRejectedValue(new Error('kapalı')),
      netWorthTrend: vi.fn().mockResolvedValue({ items: [] }),
    },
    onboardingApi: {
      rehber: vi.fn().mockResolvedValue({ adimlar: [], tamamlanan: 4, toplam: 4, tamamlandi: true, gizli: false, gorunur: false }),
      durum: vi.fn().mockResolvedValue({ demo_yuklu: false }),
    },
    coachApi: { history: vi.fn().mockResolvedValue([]), usage: vi.fn().mockResolvedValue(null) },
    userApi: { kvkkDurum: vi.fn().mockResolvedValue(null), me: vi.fn().mockResolvedValue({}) },
  };
});

import Cockpit from './panels/Cockpit.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { cockpitApi, debtsApi } from './api.js';
import { HAZIR_SORU_ANAHTARI, hazirSoruyuAl, kartSonOdemeSorusu } from './lib/kocaSor.js';

async function cizdir() {
  cockpitApi.get.mockResolvedValue(COCKPIT);
  const setActiveTab = vi.fn();
  render(<ToastProvider><Cockpit setActiveTab={setActiveTab} /></ToastProvider>);
  await screen.findByText('Yaklaşan vadeler');
  return setActiveTab;
}

beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); localStorage.clear(); });

describe('UX-013 — vade satırı eylemi', () => {
  it('borç Ödedim, alacak Geldi, kart Koça sor taşır; düzenli gider ve kimliksiz kalem taşımaz', async () => {
    await cizdir();
    expect(screen.getByRole('button', { name: 'Ali borcu: Ödedim' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Veli alacağı: Geldi' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Kart son ödeme: Koça sor' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Kira:/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Eski sunucu borcu:/ })).toBeNull();
  });

  it('Ödedim → PUT is_paid doğru kimlikle, kokpit tazelenir', async () => {
    await cizdir();
    debtsApi.update.mockResolvedValue({ id: 41, is_paid: true, settlement_account_id: 1 });
    fireEvent.click(screen.getByRole('button', { name: 'Ali borcu: Ödedim' }));
    await waitFor(() => expect(debtsApi.update).toHaveBeenCalledTimes(1));
    const [id, govde] = debtsApi.update.mock.calls[0];
    expect(id).toBe(41);
    expect(govde.is_paid).toBe(true);
    expect(govde.paid_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    await waitFor(() => expect(cockpitApi.get).toHaveBeenCalledTimes(2));   // ilk yükleme + tazeleme
    expect(await screen.findByText(/Ödeme işlendi/)).toBeInTheDocument();
  });

  it('Geldi → alacak yolu (+ tahsilat metni)', async () => {
    await cizdir();
    debtsApi.update.mockResolvedValue({ id: 42, is_paid: true, settlement_account_id: 1 });
    fireEvent.click(screen.getByRole('button', { name: 'Veli alacağı: Geldi' }));
    expect(await screen.findByText(/Tahsilat işlendi/)).toBeInTheDocument();
    expect(debtsApi.update.mock.calls[0][0]).toBe(42);
  });

  it('sunucu reddederse kokpit tazelenmez, hata görünür', async () => {
    await cizdir();
    debtsApi.update.mockRejectedValue(new Error('kapalı kayıt'));
    fireEvent.click(screen.getByRole('button', { name: 'Ali borcu: Ödedim' }));
    expect(await screen.findByText(/Ödendi işaretlenemedi/)).toBeInTheDocument();
    expect(cockpitApi.get).toHaveBeenCalledTimes(1);
  });

  it('Koça sor → hazır soru bırakılır ve koç sekmesine geçilir; Coach girdiyi alır ve siler', async () => {
    const setActiveTab = await cizdir();
    fireEvent.click(screen.getByRole('button', { name: 'Kart son ödeme: Koça sor' }));
    expect(setActiveTab).toHaveBeenCalledWith('coach');
    const soru = sessionStorage.getItem(HAZIR_SORU_ANAHTARI);
    expect(soru).toContain('Kart kartının son ödemesi 3 gün sonra');
    expect(soru).toContain('3.000');
    expect(soru).toBe(kartSonOdemeSorusu(COCKPIT.upcoming_reminders[0], '3.000,00 TL'));
    // Coach tarafı: bir kez alır, anahtar silinir (ikinci açılışta bayat soru yok)
    expect(hazirSoruyuAl()).toBe(soru);
    expect(hazirSoruyuAl()).toBe('');
  });

  it('Coach girdisi hazır soruyla başlar (kaynak bağı)', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const src = readFileSync(join(__dirname, 'panels', 'Coach.jsx'), 'utf-8');
    expect(src).toMatch(/useState\(\(\) => hazirSoruyuAl\(\)\)/);
  });
});
