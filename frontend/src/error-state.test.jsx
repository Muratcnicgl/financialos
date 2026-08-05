/**
 * P3.2 (Wave-9) — HATA DURUMU: her panel backend patlarken de ayakta kalmalı.
 *
 * Boş-durum testi (`empty-state.test.jsx`) "veri yok ama istek başarılı" halini sınar.
 * Bu dosya İKİNCİ yolu sınar: istek BAŞARISIZ. Yeni kullanıcının en sık karşılaştığı
 * senaryolar bu yoldan geçer — backend kapalı, oturum düşmüş, bayat workspace seçimi (403),
 * geçici 500. Panel bu yolda ya çöker (beyaz/kırık ekran) ya da istek döngüsüne girer.
 *
 * İki defekt sınıfı kilitlenir:
 *   BUG #218 — hata → toast → context kimliği değişir → effect yeniden koşar → SONSUZ istek.
 *   BUG #219 — hata yalnız toast'a düşer, state null kalır, panel `data.x` okurken ÇÖKER.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, waitFor, fireEvent, screen } from '@testing-library/react';

import { ToastProvider } from './components/Toast.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';

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

// Panel ilk yüklemede birkaç uç çağırır; döngü YOKSA bu sayı küçük ve sabittir.
const MAKUL_TAVAN = 12;
const COKME_METNI = /Bu panel yüklenemedi/;   // ErrorBoundary fallback'i

const PANELLER = [
  ['Cockpit', () => <Cockpit setActiveTab={() => {}} />],
  ['Koç', () => <Coach />],
  ['Hesaplar', () => <Accounts />],
  ['İşlemler', () => <Transactions />],
  ['Gelir & Borç', () => <IncomeDebt />],
  ['Kırmızı Çizgiler', () => <RedLines />],
  ['Raporlar', () => <Reports />],
  ['Akış', () => <Cashflow />],
  ['Borç Stratejisi', () => <DebtStrategy />],
  ['Hedefler', () => <Goals />],
  ['Bütçe', () => <Budget />],
  ['Aile', () => <Workspace />],
  ['Hesap', () => <Hesap />],
];

describe('P3.2 — backend hata verirken paneller (BUG #218 / #219)', () => {
  let istekler, errSpy;

  beforeEach(() => {
    istekler = [];
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      istekler.push(new URL(url, 'http://localhost').pathname);
      const json = { detail: 'Sunucu hatası' };
      return {
        ok: false, status: 500,
        headers: { get: () => 'application/json' },
        json: async () => json, text: async () => JSON.stringify(json),
      };
    }));
    const store = { fos_active_workspace_id: '1' };  // bayat/erişilemez seçim senaryosu
    vi.stubGlobal('localStorage', {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    });
    errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => { errSpy.mockRestore(); vi.unstubAllGlobals(); });

  it.each(PANELLER)('%s paneli hata yolunda çökmez', async (ad, Panel) => {
    render(<ToastProvider><ErrorBoundary><Panel /></ErrorBoundary></ToastProvider>);
    await waitFor(() => expect(istekler.length).toBeGreaterThan(0));
    await new Promise((r) => setTimeout(r, 60));

    expect(
      screen.queryByText(COKME_METNI),
      `${ad} paneli backend 500 verirken render sırasında çöktü (ErrorBoundary devreye girdi).`,
    ).toBeNull();
  });

  it.each(PANELLER)('%s paneli hata yolunda istek yağmuru başlatmaz', async (ad, Panel) => {
    render(<ToastProvider><ErrorBoundary><Panel /></ErrorBoundary></ToastProvider>);
    await waitFor(() => expect(istekler.length).toBeGreaterThan(0));
    await new Promise((r) => setTimeout(r, 150));  // döngü varsa bu sürede patlar

    expect(
      istekler.length,
      `${ad} paneli ${istekler.length} istek attı (tavan ${MAKUL_TAVAN}) — hata durumunda ` +
      `döngüye girdi:\n${JSON.stringify(istekler.slice(0, 20))}`,
    ).toBeLessThanOrEqual(MAKUL_TAVAN);
  });

  it("toast API kimliği render'lar arasında sabit kalır (BUG #218 kök nedeni)", async () => {
    // Kök-neden kilidi: kimlik oynaksa `[toast]` bağımlılığı olan HER panel aynı döngüye
    // girer. Davranış testleri geçse bile bu kilit kırılırsa yeni panel aynı tuzağa düşer.
    const { useToast } = await import('./components/Toast.jsx');
    const { useState } = await import('react');
    const kimlikler = [];
    function Prob() {
      const toast = useToast();
      const [, setN] = useState(0);
      kimlikler.push(toast);
      // Toast göster + kendini yeniden render et → kimliği render'lar arasında ölçebilelim.
      return (
        <button type="button" onClick={() => { toast.error('x'); setN((v) => v + 1); }}>
          tetikle
        </button>
      );
    }
    const { getByText } = render(<ToastProvider><Prob /></ToastProvider>);
    fireEvent.click(getByText('tetikle'));
    await waitFor(() => expect(kimlikler.length).toBeGreaterThan(1));

    const farkli = kimlikler.filter((k) => k !== kimlikler[0]).length;
    expect(farkli, "toast context değeri her render'da yeniden yaratılıyor").toBe(0);
  });
});
