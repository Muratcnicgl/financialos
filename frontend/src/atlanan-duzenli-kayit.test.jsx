/**
 * BUG #273 — vadesi gelip de ÖNERİYE DÖNÜŞEMEYEN düzenli kayıt kullanıcıya GÖRÜNÜR.
 *
 * Ölçüm: `trigger-due` uçları reddi `logger.error`a yazıp `{"triggered": []}` dönüyordu;
 * Cockpit da yalnız `triggered` alanını okuyordu. Yani kullanıcı, kirasının önerilmediğini
 * ancak ay sonunda bakiyesi tutmayınca fark ederdi — üstelik `last_triggered` yazılmadığı
 * için istek her gün yeniden denenip her gün sessizce düşüyordu.
 *
 * Backend tarafı `tests/test_aksiyon_sinyali_kapisi.py` ile kilitli; burası sinyalin
 * KULLANICIYA ULAŞTIĞINI kilitler (L21 sınıfı: sinyal hesaplanıp karar katmanına hiç
 * ulaşmaması, hiç hesaplanmamasıyla aynı şeydir).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import bosKullanici from './__fixtures__/bos-kullanici.json';
import { ToastProvider } from './components/Toast.jsx';
import Cockpit from './panels/Cockpit.jsx';

const ATLANAN = {
  triggered: [],
  atlanan: [{ id: 4, ad: 'Kira', neden: 'Hangi hesaptan? Hesabı yazarsan hemen kaydederim.' }],
};

function fetchMock(gelirCevabi, giderCevabi) {
  return vi.fn(async (url) => {
    const yol = new URL(url, 'http://localhost').pathname;
    let govde = bosKullanici[yol];
    if (yol === '/api/incomes/trigger-due') govde = gelirCevabi;
    if (yol === '/api/expenses/recurring/trigger-due') govde = giderCevabi;
    const bulundu = govde !== undefined;
    return {
      ok: bulundu,
      status: bulundu ? 200 : 404,
      headers: { get: () => 'application/json' },
      json: async () => (bulundu ? govde : { detail: 'Bulunamadı' }),
      text: async () => JSON.stringify(bulundu ? govde : { detail: 'Bulunamadı' }),
    };
  });
}

describe('BUG #273 — atlanan düzenli kayıt sessiz kalmaz', () => {
  beforeEach(() => {
    const store = {};
    vi.stubGlobal('localStorage', {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    });
  });

  afterEach(() => vi.unstubAllGlobals());

  it('atlanan kaydın ADI ve NEDENİ ekranda yazar', async () => {
    vi.stubGlobal('fetch', fetchMock({ triggered: [], atlanan: [] }, ATLANAN));
    render(<ToastProvider><Cockpit setActiveTab={() => {}} /></ToastProvider>);

    const uyari = await screen.findByTestId('atlanan-duzenli-kayitlar');
    expect(uyari).toBeVisible();
    expect(uyari).toHaveTextContent('Kira');
    expect(uyari).toHaveTextContent('Hangi hesaptan?');
  });

  it('gelir ve gider tetikleyicilerinin atlananları BİRLEŞTİRİLİR', async () => {
    vi.stubGlobal('fetch', fetchMock(
      { triggered: [], atlanan: [{ id: 9, ad: 'Maaş', neden: 'Nakit hesabın yok.' }] },
      ATLANAN,
    ));
    render(<ToastProvider><Cockpit setActiveTab={() => {}} /></ToastProvider>);

    const uyari = await screen.findByTestId('atlanan-duzenli-kayitlar');
    expect(uyari).toHaveTextContent('Maaş');
    expect(uyari).toHaveTextContent('Kira');
    expect(uyari).toHaveTextContent('2 düzenli kayıt');
  });

  it('atlanan yoksa uyarı HİÇ çizilmez (gürültü üretmez)', async () => {
    vi.stubGlobal('fetch', fetchMock({ triggered: [], atlanan: [] }, { triggered: [], atlanan: [] }));
    const { container } = render(<ToastProvider><Cockpit setActiveTab={() => {}} /></ToastProvider>);
    await waitFor(() => expect(container.textContent.length).toBeGreaterThan(0));
    expect(screen.queryByTestId('atlanan-duzenli-kayitlar')).toBeNull();
  });
});
