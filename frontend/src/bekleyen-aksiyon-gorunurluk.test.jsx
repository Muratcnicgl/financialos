/**
 * BUG #266 — onayladığın şey GÖRÜNÜR olmalı.
 *
 * Ölçüm: `add_transaction` payload'ı okunabilir bir tabloya çevriliyordu ama DİĞER ALTI tür
 * (kart ödemesi, bakiye düzeltmesi, fon fiyatı, yatırım satışı, borç kapatma) KAPALI bir
 * `<details>` içinde ham JSON'du. Yani kullanıcının onayladığı para hareketlerinde ekranda
 * yalnız koçun yazdığı ÖZET vardı; özet ile payload birbirini tutmasa (ölçüm: summary "320 TL",
 * payload 3200) kullanıcı bunu göremezdi. Backend artık çelişkiyi reddediyor; burası da
 * kullanıcının gerçekten ne onayladığını göstermesini kilitler.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import PendingActions from './components/PendingActions.jsx';

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return {
    ...gercek,
    actionsApi: { approve: vi.fn(), reject: vi.fn(), edit: vi.fn() },
  };
});

const HESAPLAR = [
  { id: 7, name: 'Garanti Kart' },
  { id: 3, name: 'Nakit Kasa' },
];

function kartOdemesi() {
  return [{
    id: 1,
    action_type: 'pay_credit_card',
    summary: 'Kart borcuna 19.700,50 TL ödeme kaydedildi',
    payload: JSON.stringify({ card_account_id: 7, amount: 19700.5, source_account_id: 3 }),
  }];
}

describe('BUG #266 — para hareketinin alanları onay ekranında GÖRÜNÜR', () => {
  beforeEach(() => vi.clearAllMocks());

  it('kart ödemesinde tutar açıkça yazılır (kapalı <details> içinde saklanmaz)', () => {
    render(<PendingActions actions={kartOdemesi()} accounts={HESAPLAR} onResolved={() => {}} />);
    // Özet metninde de tutar geçer; aranan şey ALAN SATIRIDIR (etiket + biçimli değer).
    expect(screen.getByText('Tutar')).toBeVisible();
    expect(screen.getAllByText(/19\.700,50/).length).toBeGreaterThanOrEqual(2);
  });

  it('hesap kimliği ham id değil HESAP ADI olarak gösterilir', () => {
    render(<PendingActions actions={kartOdemesi()} accounts={HESAPLAR} onResolved={() => {}} />);
    expect(screen.getByText('Garanti Kart')).toBeVisible();
    expect(screen.getByText('Nakit Kasa')).toBeVisible();
  });

  it('sözlükte olmayan alan HAM adıyla yine de gösterilir (sessizce düşmez)', () => {
    const actions = [{
      id: 2,
      action_type: 'update_account_balance',
      summary: 'Bakiye 1.000,00 TL olarak güncellendi',
      payload: JSON.stringify({ account_id: 3, new_balance: 1000, bilinmeyen_alan: 'x' }),
    }];
    render(<PendingActions actions={actions} accounts={HESAPLAR} onResolved={() => {}} />);
    expect(screen.getByText('bilinmeyen_alan')).toBeVisible();
    expect(screen.getByText('x')).toBeVisible();
  });

  it('bozuk JSON payload paneli çökertmez', () => {
    const actions = [{
      id: 3, action_type: 'update_fund_price',
      summary: 'Fon fiyatı güncellendi', payload: '{bozuk',
    }];
    render(<PendingActions actions={actions} accounts={HESAPLAR} onResolved={() => {}} />);
    expect(screen.getByText(/Fon fiyatı güncellendi/)).toBeVisible();
  });
});
