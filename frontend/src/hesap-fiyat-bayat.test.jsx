/**
 * D23 / BUG #239 — sınıf taraması: Hesaplar paneli bayat fiyatı "Güncel fiyat" diye
 * etiketliyordu.
 *
 * Koç tarafındaki asıl bulgu (bayat fiyattan "yatırım değerin X TL, %Y kârdasın")
 * kapatılırken aynı sınıfın ikinci yüzeyi bulundu: panel `current_price`'ı KOŞULSUZ
 * "Güncel fiyat" başlığıyla basıyordu ve yaşı hiç göstermiyordu. Sağlayıcı haftalarca
 * sussa da kullanıcı ekranda "güncel" yazısını görüyordu — satış kararı tam burada verilir.
 *
 * Yaş metni istemcide HESAPLANMAZ; backend türetir (tek kaynak: fund_tracker) — bu testler
 * panelin o sözleşmeyi gerçekten gösterdiğini kilitler.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return {
    ...gercek,
    accountsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
    fundPriceApi: { freshness: vi.fn().mockResolvedValue({ items: [] }) },
  };
});

import Accounts from './panels/Accounts.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { accountsApi } from './api.js';

const BAYAT_FON = {
  id: 1, user_id: 1, name: 'TLY Fonu', account_type: 'investment', balance: 31342.86,
  fund_code: 'TLY', lot_count: 6, cost_per_lot: 4000, current_price: 5223.81,
  is_emanet: false, last_price_update: '2026-07-07T10:00:00+00:00',
  fiyat_bayat: true, fiyat_yas: '30 gün önce',
};

const TAZE_FON = {
  ...BAYAT_FON, id: 2, name: 'Taze Fon', fund_code: 'XYZ',
  fiyat_bayat: false, fiyat_yas: '2 saat önce',
};

beforeEach(() => vi.clearAllMocks());

describe('Hesaplar paneli — fiyat tazeliği', () => {
  it('bayat fiyatı "Güncel fiyat" diye etiketlemez', async () => {
    accountsApi.list.mockResolvedValue([BAYAT_FON]);
    render(<ToastProvider><Accounts /></ToastProvider>);
    expect(await screen.findByText('TLY Fonu')).toBeInTheDocument();
    expect(screen.queryByText('Güncel fiyat')).not.toBeInTheDocument();
    expect(screen.getByText('Fiyat (bayat)')).toBeInTheDocument();
  });

  it('fiyatın yaşını gösterir (kullanıcı neye baktığını bilir)', async () => {
    accountsApi.list.mockResolvedValue([BAYAT_FON]);
    render(<ToastProvider><Accounts /></ToastProvider>);
    expect(await screen.findByText(/30 gün önce/)).toBeInTheDocument();
  });

  it('taze fiyatta "Güncel fiyat" etiketi korunur (koşulsuz uyarı gürültüdür)', async () => {
    accountsApi.list.mockResolvedValue([TAZE_FON]);
    render(<ToastProvider><Accounts /></ToastProvider>);
    expect(await screen.findByText('Taze Fon')).toBeInTheDocument();
    expect(screen.getByText('Güncel fiyat')).toBeInTheDocument();
    expect(screen.queryByText('Fiyat (bayat)')).not.toBeInTheDocument();
    expect(screen.getByText(/2 saat önce/)).toBeInTheDocument();
  });

  it('nakit hesapta fiyat satırı hiç çıkmaz', async () => {
    accountsApi.list.mockResolvedValue([{
      id: 3, user_id: 1, name: 'Nakit', account_type: 'cash', balance: 1000,
      is_emanet: false, fiyat_bayat: false, fiyat_yas: null,
    }]);
    render(<ToastProvider><Accounts /></ToastProvider>);
    expect(await screen.findByText('Nakit')).toBeInTheDocument();
    expect(screen.queryByText('Fiyat yaşı')).not.toBeInTheDocument();
  });
});
