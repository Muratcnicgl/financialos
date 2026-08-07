/**
 * BUG #262 (P3.3) — İLK KURULUM REHBERİ: ölü CTA + ilk adımdan sonra kaybolma.
 *
 * İki defekt vardı ve ikisi de SESSİZDİ (tarayıcı hata vermez, süit yeşil kalır — L28):
 *   (a) Kart yalnız `accounts.length === 0` iken çiziliyordu; kullanıcı ilk hesabını ekler
 *       eklemez kalan üç adım hiç yönlendirilmiyordu.
 *   (b) Birincil düğme `<a href="#accounts">` idi; uygulama hash-router kullanmıyor
 *       (`App.jsx` `activeTab` state'i) → düğme HİÇBİR ŞEY yapmıyordu.
 *
 * Kilitlenen sözleşme:
 *   1. Rehber, adımlar bitene kadar görünür (backend `gorunur` der, arayüz uydurmaz).
 *   2. Her adım düğmesi GERÇEKTEN sekme değiştirir (setActiveTab çağrılır).
 *   3. Rehberde ölü `href="#..."` bağlantısı YOKTUR.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

import Onboarding from './components/Onboarding.jsx';

const ADIMLAR = [
  { anahtar: 'hesap', baslik: 'Kendi hesabını ekle', aciklama: 'a', sekme: 'accounts', tamam: false },
  { anahtar: 'islem', baslik: 'İlk işlemini gir', aciklama: 'b', sekme: 'transactions', tamam: false },
  { anahtar: 'kural', baslik: 'Kendi kuralını yaz', aciklama: 'c', sekme: 'redlines', tamam: false },
  { anahtar: 'koc', baslik: 'Koça ilk sorunu sor', aciklama: 'd', sekme: 'coach', tamam: false },
];

function rehberGovdesi(tamamAnahtarlari = [], ek = {}) {
  const adimlar = ADIMLAR.map((a) => ({ ...a, tamam: tamamAnahtarlari.includes(a.anahtar) }));
  const tamamlanan = adimlar.filter((a) => a.tamam).length;
  const tamamlandi = tamamlanan === adimlar.length;
  const gizli = ek.gizli ?? false;
  return {
    adimlar, tamamlanan, toplam: adimlar.length, tamamlandi, gizli,
    gorunur: !tamamlandi && !gizli, ...ek,
  };
}

function stubFetch({ rehber, demo = { yuklu: false, satir_sayisi: 0 }, kayit = [] }) {
  vi.stubGlobal('fetch', vi.fn(async (url, opts) => {
    const yol = new URL(url, 'http://localhost').pathname;
    kayit.push({ yol, method: opts?.method || 'GET' });
    const govde = yol.endsWith('/rehber') ? rehber : demo;
    return {
      ok: true, status: 200,
      headers: { get: () => 'application/json' },
      json: async () => govde,
      text: async () => JSON.stringify(govde),
    };
  }));
  return kayit;
}

afterEach(() => vi.unstubAllGlobals());

describe('BUG #262 — ilk kurulum rehberi', () => {
  it('dört adımı da çizer ve ilerlemeyi gösterir', async () => {
    stubFetch({ rehber: rehberGovdesi() });
    render(<Onboarding setActiveTab={() => {}} />);

    expect(await screen.findByText('Hoş geldin — buradan başla')).toBeInTheDocument();
    expect(screen.getByTestId('rehber-ilerleme')).toHaveTextContent('0/4 adım');
    for (const a of ADIMLAR) {
      expect(screen.getByTestId(`rehber-adim-${a.anahtar}`)).toBeInTheDocument();
    }
  });

  it('ilk adım tamamlandıktan sonra KAYBOLMAZ — kalan adımlar yönlendirilir', async () => {
    // BUG #262(a) regresyon kapısı.
    stubFetch({ rehber: rehberGovdesi(['hesap']) });
    render(<Onboarding setActiveTab={() => {}} />);

    expect(await screen.findByText('Hoş geldin — buradan başla')).toBeInTheDocument();
    expect(screen.getByTestId('rehber-ilerleme')).toHaveTextContent('1/4 adım');
    expect(screen.getByTestId('rehber-adim-hesap')).toHaveAttribute('data-tamam', '1');
    expect(screen.getByTestId('rehber-adim-islem')).toHaveAttribute('data-tamam', '0');
  });

  it('adım düğmesi GERÇEKTEN sekme değiştirir (ölü CTA kapısı)', async () => {
    // BUG #262(b) regresyon kapısı: eski kart `<a href="#accounts">` idi, hiçbir şey yapmıyordu.
    stubFetch({ rehber: rehberGovdesi() });
    const setActiveTab = vi.fn();
    const { container } = render(<Onboarding setActiveTab={setActiveTab} />);

    const satir = await screen.findByTestId('rehber-adim-kural');
    fireEvent.click(satir.querySelector('button'));
    expect(setActiveTab).toHaveBeenCalledWith('redlines');

    const oluBaglanti = container.querySelector('a[href^="#"]');
    expect(oluBaglanti, 'rehberde ölü hash bağlantısı var').toBeNull();
  });

  it('her adımın düğmesi kendi sekmesini açar', async () => {
    stubFetch({ rehber: rehberGovdesi() });
    const setActiveTab = vi.fn();
    render(<Onboarding setActiveTab={setActiveTab} />);
    await screen.findByTestId('rehber-adim-hesap');

    for (const a of ADIMLAR) {
      fireEvent.click(screen.getByTestId(`rehber-adim-${a.anahtar}`).querySelector('button'));
    }
    expect(setActiveTab.mock.calls.map((c) => c[0]))
      .toEqual(['accounts', 'transactions', 'redlines', 'coach']);
  });

  it('tamamlanan adımda "Git" düğmesi kalmaz', async () => {
    stubFetch({ rehber: rehberGovdesi(['hesap']) });
    render(<Onboarding setActiveTab={() => {}} />);
    const satir = await screen.findByTestId('rehber-adim-hesap');
    expect(satir.querySelector('button')).toBeNull();
  });

  it('backend "görünür değil" derse hiç çizmez', async () => {
    stubFetch({ rehber: rehberGovdesi(['hesap', 'islem', 'kural', 'koc']) });
    const { container } = render(<Onboarding setActiveTab={() => {}} />);
    await waitFor(() => expect(container.textContent).not.toContain('Hoş geldin'));
  });

  it('gizlenmiş rehber çizilmez ama demo şeridi görünmeye devam eder', async () => {
    // Kullanıcı kilitlenmemeli: rehberi kapatsa bile örnek veriyi kaldırma yolu durur.
    stubFetch({
      rehber: rehberGovdesi([], { gizli: true }),
      demo: { yuklu: true, satir_sayisi: 8 },
    });
    render(<Onboarding setActiveTab={() => {}} />);
    expect(await screen.findByText(/Örnek veriyi kaldır/)).toBeInTheDocument();
    expect(screen.queryByText('Hoş geldin — buradan başla')).toBeNull();
  });

  it('"Rehberi gizle" PATCH gönderir', async () => {
    const kayit = stubFetch({ rehber: rehberGovdesi() });
    render(<Onboarding setActiveTab={() => {}} />);
    fireEvent.click(await screen.findByText(/Rehberi gizle/));
    await waitFor(() => expect(
      kayit.some((k) => k.yol === '/api/onboarding/rehber' && k.method === 'PATCH')
    ).toBe(true));
  });

  it('rehber ucu düşerse panel çökmez', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('ağ yok'); }));
    const { container } = render(<Onboarding setActiveTab={() => {}} />);
    await waitFor(() => expect(container).toBeTruthy());
    expect(container.textContent).not.toContain('Hoş geldin');
  });
});
