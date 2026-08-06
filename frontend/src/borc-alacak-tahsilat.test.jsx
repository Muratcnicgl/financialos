/**
 * BUG #241 — "Ödendi" işaretlenen alacak nakde geçmiyordu.
 *
 * Backend tarafı düzeldi (PUT /api/debts/{id} nakit ayağını da uygular). Panel tarafında
 * kalan risk: bakiyenin NEDEN değiştiği görünmezse kullanıcı bu kez ters yönde şüpheye
 * düşer ("param neden arttı?"). Bu dosya panelin sözleşmesini kilitler:
 *   - tahsilat işaretlenince nereye ne kadar işlendiği söylenir,
 *   - nakit hesap yoksa SESSİZ kalınmaz (uyarı),
 *   - kapanmış kayıt hangi hesaba işlendiğini satırında taşır,
 *   - silme onayı nakit etkisinin geri sarılacağını ÖNCEDEN söyler.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

import IncomeDebt from './panels/IncomeDebt.jsx';
import { ToastProvider } from './components/Toast.jsx';

const HESAP = { id: 7, name: 'Enpara', account_type: 'cash', balance: 10000, is_emanet: false };

const ALACAK = {
  id: 1, counterparty: 'Borçlu', direction: 'receivable', amount: 5000,
  description: null, due_date: '2026-08-10', is_paid: false, paid_date: null,
  settlement_account_id: null, created_at: '2026-08-01T10:00:00+00:00',
};

const ODENMIS_ALACAK = {
  ...ALACAK, id: 2, is_paid: true, paid_date: '2026-08-06', settlement_account_id: HESAP.id,
};

function makeFetchMock({ debts, accounts = [HESAP], kayit }) {
  return vi.fn(async (url, init = {}) => {
    const u = new URL(url, 'http://localhost');
    kayit.push({ yol: u.pathname, method: init.method || 'GET', body: init.body });

    let govde;
    if (u.pathname === '/api/debts') govde = debts;
    else if (u.pathname === '/api/accounts') govde = accounts;
    else if (u.pathname === '/api/incomes' || u.pathname === '/api/expenses') govde = [];
    else if (/^\/api\/debts\/\d+$/.test(u.pathname) && init.method === 'PUT') {
      const yama = JSON.parse(init.body || '{}');
      // Backend sözleşmesi: ödendi işaretlenince nakit ayağı uygulanır ve İZ bırakır.
      govde = {
        ...debts[0], ...yama,
        settlement_account_id: yama.is_paid && accounts.length ? accounts[0].id : null,
      };
    } else if (/^\/api\/debts\/\d+$/.test(u.pathname) && init.method === 'DELETE') {
      govde = null;
    } else govde = [];

    return {
      ok: true, status: 200, headers: { get: () => 'application/json' },
      json: async () => govde, text: async () => JSON.stringify(govde),
    };
  });
}

async function panelAc(secenekler) {
  const kayit = [];
  vi.stubGlobal('fetch', makeFetchMock({ ...secenekler, kayit }));
  render(<ToastProvider><IncomeDebt /></ToastProvider>);
  fireEvent.click(await screen.findByRole('button', { name: /Borç \/ Alacak|Borç\/Alacak/ }));
  return kayit;
}

/** Panelin varsayılan filtresi "Bekleyen" — kapanmış kayda bakmak için "Ödenmiş"e geç. */
async function odenmisFiltresi() {
  const secim = await screen.findByDisplayValue('Bekleyen');
  fireEvent.change(secim, { target: { value: 'paid' } });
}

describe('BUG #241 — tahsilat nakde yansır ve GÖRÜNÜR', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('tahsilat işaretlenince hangi hesaba ne kadar işlendiği söylenir', async () => {
    await panelAc({ debts: [ALACAK] });

    fireEvent.click(await screen.findByTitle('Ödendi olarak işaretle'));

    expect(await screen.findByText(/Tahsilat işlendi/)).toBeInTheDocument();
    expect(screen.getByText(/Enpara bakiyesine yansıdı/)).toBeInTheDocument();
  });

  it('nakit hesap yoksa sessiz kalınmaz — bakiyenin değişmediği söylenir', async () => {
    await panelAc({ debts: [ALACAK], accounts: [] });

    fireEvent.click(await screen.findByTitle('Ödendi olarak işaretle'));

    expect(await screen.findByText(/nakit bakiyesi değişmedi/)).toBeInTheDocument();
  });

  it('kapanmış kayıt hangi hesaba işlendiğini satırında taşır', async () => {
    await panelAc({ debts: [ODENMIS_ALACAK] });

    await odenmisFiltresi();
    expect(await screen.findByText(/Nakde geçti: Enpara/)).toBeInTheDocument();
  });

  it('silme onayı nakit etkisinin geri sarılacağını önceden söyler', async () => {
    await panelAc({ debts: [ODENMIS_ALACAK] });

    await odenmisFiltresi();
    fireEvent.click(await screen.findByTitle('Sil'));

    expect(await screen.findByText(/nakit karşılığı da geri alınacak/)).toBeInTheDocument();
    // Yön ve tutar açıkça yazılı olmalı (alacak silinince nakit DÜŞER).
    expect(screen.getByText(/TL düşecek/)).toBeInTheDocument();
    expect(screen.getByText(/TL düşecek/).textContent).toMatch(/5[.,]000/);
  });

  it('kapanmış kayıt geri alınabilir ve nakdin geri sarıldığı söylenir', async () => {
    const kayit = await panelAc({ debts: [ODENMIS_ALACAK] });
    await odenmisFiltresi();

    fireEvent.click(await screen.findByTitle('Ödendi işaretini geri al'));

    await waitFor(() => {
      const put = kayit.find(k => k.method === 'PUT' && k.yol === `/api/debts/${ODENMIS_ALACAK.id}`);
      expect(put).toBeTruthy();
      expect(JSON.parse(put.body)).toEqual({ is_paid: false });
    });
    expect(await screen.findByText(/geri alındı/)).toBeInTheDocument();
    expect(screen.getByText(/Enpara: −5[.,]000.*geri sarıldı/)).toBeInTheDocument();
  });

  it('ödenmemiş kaydın silinmesinde nakit uyarısı ÇIKMAZ', async () => {
    await panelAc({ debts: [ALACAK] });

    fireEvent.click(await screen.findByTitle('Sil'));

    expect(await screen.findByText(/Bu kayıt silinecek/)).toBeInTheDocument();
    expect(screen.queryByText(/nakit karşılığı da geri alınacak/)).not.toBeInTheDocument();
  });
});
