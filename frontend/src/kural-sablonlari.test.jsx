/**
 * UX-038 (BUG #481): boş "Kırmızı Çizgiler" tipik başlangıç şablonları sunar.
 *
 * Ölçüm (14 Eyl 2026): boş durum yalnız "İlk kuralı ekle" diyordu; kullanıcı boş bir formla
 * baş başaydı. Kategori seti tarafı ZATEN çözümlüydü (ADR-046 `kategorileri_tohumla`). Burada:
 *  - kural yokken 3 şablon görünür; hesap yoksa "Dokunulmaz hesap" gizlenir (seçecek şey yok),
 *  - şablona tıklayınca form BAŞLIK/AÇIKLAMA/KURAL TİPİ dolu, TUTAR BOŞ açılır (ürün sayı uydurmaz),
 *  - kayıt, kullanıcının yazdığı tutarla POST edilir,
 *  - kural varken şablon listesi görünmez (gürültü değil, başlangıç yardımı).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import RedLines from './panels/RedLines.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { KURAL_SABLONLARI, uygunSablonlar } from './lib/kuralSablonlari.js';

function fetchSahtesi({ kurallar = [], hesaplar = [], postlar }) {
  return vi.fn(async (url, init = {}) => {
    const u = new URL(url, 'http://localhost');
    let govde = [];
    if (u.pathname === '/api/checkpoints' && (init.method || 'GET') === 'GET') govde = kurallar;
    else if (u.pathname === '/api/checkpoints' && init.method === 'POST') {
      const b = JSON.parse(init.body || '{}');
      postlar.push(b);
      govde = { id: 99, is_active: true, created_at: '2026-09-14T00:00:00+00:00', ...b };
      return { ok: true, status: 201, headers: { get: () => 'application/json' }, json: async () => govde, text: async () => JSON.stringify(govde) };
    } else if (u.pathname === '/api/accounts') govde = hesaplar;
    return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => govde, text: async () => JSON.stringify(govde) };
  });
}

let postlar;
beforeEach(() => { postlar = []; localStorage.clear(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('UX-038 — kural şablonları', () => {
  it('uygunSablonlar: hesap yoksa "Dokunulmaz hesap" gizli, varsa 3', () => {
    expect(KURAL_SABLONLARI).toHaveLength(3);
    expect(uygunSablonlar([]).map((s) => s.anahtar)).toEqual(['nakit_tabani', 'tek_harcama_tavani']);
    expect(uygunSablonlar([{ id: 1 }])).toHaveLength(3);
    // her şablon dayatılan bir kural tipine bağlı, tutar taşımaz
    for (const s of KURAL_SABLONLARI) {
      expect(['min_cash_floor', 'max_single_expense', 'account_untouchable']).toContain(s.sablon.rule_type);
      expect(s.sablon.rule_params).toBeUndefined();
    }
  });

  it('kural yokken şablonlar görünür; varken görünmez', async () => {
    vi.stubGlobal('fetch', fetchSahtesi({ postlar }));
    const { unmount } = render(<ToastProvider><RedLines /></ToastProvider>);
    expect(await screen.findByTestId('kural-sablonlari')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Nakit tabanı|Tek harcama tavanı/ })).toHaveLength(2);
    unmount();
    vi.stubGlobal('fetch', fetchSahtesi({ postlar, kurallar: [{ id: 1, title: 'Var', description: 'x', checkpoint_type: 'rule', priority: 2, is_active: true, rule_type: null, rule_params: null, created_at: '2026-08-01T10:00:00+00:00' }] }));
    render(<ToastProvider><RedLines /></ToastProvider>);
    await screen.findByText('Var');
    expect(screen.queryByTestId('kural-sablonlari')).toBeNull();
  });

  it('şablon → form dolu, tutar boş; kullanıcı tutarı yazar, POST şablon yapısıyla gider', async () => {
    vi.stubGlobal('fetch', fetchSahtesi({ postlar }));
    render(<ToastProvider><RedLines /></ToastProvider>);
    fireEvent.click(await screen.findByRole('button', { name: /Nakit tabanı/ }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Yeni kural');
    const baslik = screen.getByDisplayValue('Nakit tabanı');
    expect(baslik).toBeInTheDocument();
    const tutar = screen.getByLabelText(/^Tutar/);
    expect(tutar.value).toBe('');
    const kaydet = screen.getByRole('button', { name: /Kaydet|Oluştur|Ekle/ });
    fireEvent.click(kaydet);   // tutarsız kaydetme: sunucuya gitmez
    expect(postlar).toHaveLength(0);
    fireEvent.change(tutar, { target: { value: '8.000' } });
    fireEvent.click(kaydet);
    await waitFor(() => expect(postlar).toHaveLength(1));
    expect(postlar[0]).toMatchObject({ title: 'Nakit tabanı', checkpoint_type: 'rule', priority: 1, rule_type: 'min_cash_floor', rule_params: { amount: 8000 } });
  });
});
