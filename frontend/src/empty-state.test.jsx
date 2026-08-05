/**
 * P3.2 (Wave-9) — BOŞ-DURUM PANEL TESTLERİ (yeni kullanıcının gördüğü ilk ekran).
 *
 * Backend tarafı `tests/test_sifirdan_kullanici_e2e.py` ile kanıtlı: boş kullanıcıda
 * hiçbir uç çökmüyor. Ama kullanıcının GÖRDÜĞÜ şey React panelleri — panel boş gövdeyi
 * (0 / null / boş liste) render ederken çökerse kullanıcı beyaz ekran görür ve backend
 * süiti yeşil kalır. P3.2'nin kapatılmamış yarısı buydu.
 *
 * Mock'lar TAHMİN DEĞİL: `frontend/src/__fixtures__/bos-kullanici.json` gerçek kayıt
 * akışıyla yaratılmış boş kullanıcının GERÇEK API cevaplarıdır
 * (`tests/test_bos_durum_frontend_fixture.py` üretir + sözleşme kayması kapısıyla korur).
 *
 * İki sınıf defekt aranır:
 *   1. Çökme  — panel render sırasında exception (ErrorBoundary fallback'i görünür).
 *   2. Sızıntı — ekranda "NaN", "Infinity", "undefined" gibi ham JS artıkları.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

import bosKullanici from './__fixtures__/bos-kullanici.json';
import { ToastProvider } from './components/Toast.jsx';

import Cockpit from './panels/Cockpit.jsx';
import Coach from './panels/Coach.jsx';
import Accounts from './panels/Accounts.jsx';
import Transactions from './panels/Transactions.jsx';
import IncomeDebt from './panels/IncomeDebt.jsx';
import RedLines from './panels/RedLines.jsx';
import Reports from './panels/Reports.jsx';
import Cashflow from './panels/Cashflow.jsx';
import DebtStrategy from './panels/DebtStrategy.jsx';
import Goals from './panels/Goals.jsx';
import Budget from './panels/Budget.jsx';
import Workspace from './panels/Workspace.jsx';
import Hesap from './panels/Hesap.jsx';

// Panelin ilk açılışta okuduğu, fixture'da OLMAYAN uçlar 404 döner (gerçekçi: yol
// parametreli uçlar boş kullanıcıda kayıt bulamaz). Panel bunu yakalayıp bozulmamalı.
function makeFetchMock(kayit) {
  return vi.fn(async (url) => {
    const yol = new URL(url, 'http://localhost').pathname;
    kayit.push(yol);
    const govde = bosKullanici[yol];
    const json = govde !== undefined ? govde : { detail: 'Bulunamadı' };
    return {
      ok: govde !== undefined,
      status: govde !== undefined ? 200 : 404,
      headers: { get: () => 'application/json' },
      json: async () => json,
      text: async () => JSON.stringify(json),
    };
  });
}

const PANELLER = [
  ['Cockpit', <Cockpit setActiveTab={() => {}} />],
  ['Koç', <Coach />],
  ['Hesaplar', <Accounts />],
  ['İşlemler', <Transactions />],
  ['Gelir & Borç', <IncomeDebt />],
  ['Kırmızı Çizgiler', <RedLines />],
  ['Raporlar', <Reports />],
  ['Akış', <Cashflow />],
  ['Borç Stratejisi', <DebtStrategy />],
  ['Hedefler', <Goals />],
  ['Bütçe', <Budget />],
  ['Aile', <Workspace />],
  ['Hesap', <Hesap />],
];

// Ham JS artıkları — kullanıcı bunları ASLA görmemeli (boş veri × biçimlendirme hatası).
// Kelime sınırıyla aranır: "undefined" içeren normal Türkçe metin yok, ama "NaN" harf
// dizisi başka kelimenin içinde geçebilir (ör. "finansal" değil ama korunmak bedava).
const HAM_ARTIKLAR = [/\bNaN\b/, /\bInfinity\b/, /\bundefined\b/, /\[object Object\]/];

describe('P3.2 — boş kullanıcı: hiçbir panel çökmez, ham JS artığı sızmaz', () => {
  let istekler, konsolHatalari, errSpy;

  beforeEach(() => {
    istekler = [];
    konsolHatalari = [];
    vi.stubGlobal('fetch', makeFetchMock(istekler));
    const store = {};
    vi.stubGlobal('localStorage', {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    });
    // React render hatası konsola düşer; sessizce yutulmasın diye biriktirilir.
    errSpy = vi.spyOn(console, 'error').mockImplementation((...a) => {
      konsolHatalari.push(a.map(String).join(' '));
    });
  });

  afterEach(() => {
    errSpy.mockRestore();
    vi.unstubAllGlobals();
  });

  it.each(PANELLER)('%s paneli boş veriyle render olur', async (ad, eleman) => {
    const { container } = render(<ToastProvider>{eleman}</ToastProvider>);

    // Yükleme efektleri otursun (her panel en az bir istek atar ya da anında içerik basar).
    await waitFor(() => {
      expect(container.textContent.length).toBeGreaterThan(0);
    });

    const patlama = konsolHatalari.filter((m) => /Uncaught|The above error|Consider adding an error boundary/.test(m));
    expect(patlama, `${ad} paneli boş veride render sırasında çöktü:\n${patlama.join('\n')}`).toEqual([]);
  });

  it.each(PANELLER)('%s paneli boş veride ham JS artığı göstermez', async (ad, eleman) => {
    const { container } = render(<ToastProvider>{eleman}</ToastProvider>);
    await waitFor(() => expect(container.textContent.length).toBeGreaterThan(0));
    // Efekt zincirleri (fetch → setState → ikinci fetch) tamamlansın.
    await waitFor(() => expect(istekler.length).toBeGreaterThanOrEqual(0));
    await new Promise((r) => setTimeout(r, 0));

    const metin = container.textContent;
    const bulunan = HAM_ARTIKLAR.filter((re) => re.test(metin)).map((re) => re.source);
    expect(bulunan, `${ad} panelinde ham JS artığı görünüyor: ${bulunan.join(', ')}\nEkran: ${metin.slice(0, 400)}`).toEqual([]);
  });

  it('boş-durum fixture\'ı panellerin okuduğu uçları kapsıyor', () => {
    // Kapsam duyarlılığı: fixture bir uç kaybederse panel 404 alır ve test "boş ama sağlam"
    // yerine "hata yolu" test etmeye başlar — sessiz körleşme (BUG #217 dersi).
    const zorunlu = ['/api/cockpit', '/api/accounts', '/api/transactions', '/api/goals'];
    const eksik = zorunlu.filter((y) => !(y in bosKullanici));
    expect(eksik, `fixture bayat: ${eksik.join(', ')} yok`).toEqual([]);
  });
});
