/**
 * A11Y-009 KAPISI (BUG #449) — FORM HATASI EKRAN OKUYUCUYA DUYURULUR.
 *
 * Ölçülen (13 Eyl 2026): 13 form-düzeyi hata paragrafı (`{error && <p …>}`) yalnız renkle
 * görünüyordu; `role="alert"` 0 kez — ekran okuyucu hatayı duymuyordu (WCAG 3.3.1/4.1.3).
 * Alan-düzeyi `aria-invalid` uygulanmadı: doğrulama sunucuda, hata FORM düzeyinde döner
 * (alan bilgisi yok); alan-bazlı doğrulama hatası (API-013) geldiğinde açılır.
 *
 * Kilitlenen: `{x && <p …>{x}</p>}` biçimindeki her hata paragrafı `role="alert"` taşır;
 * hesap formunda sunucu hatası `role=alert` ile görünür.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import bosKullanici from './__fixtures__/bos-kullanici.json';
import { ToastProvider } from './components/Toast.jsx';
import Accounts from './panels/Accounts.jsx';

const KOK = join(__dirname);
function jsxDosyalari(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) jsxDosyalari(yol, out);
    else if (ad.endsWith('.jsx') && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

describe('A11Y-009 — form hatası duyurulur', () => {
  it('her form-düzeyi hata paragrafı role="alert" taşır', () => {
    const ihlal = []; let sayi = 0;
    for (const f of jsxDosyalari(KOK)) {
      readFileSync(f, 'utf-8').split('\n').forEach((s, i) => {
        const m = s.match(/\{(err|error|hata|editErr) && <p\b([^>]*)>/);
        if (!m) return;
        sayi += 1;
        if (!/role="alert"/.test(m[2])) ihlal.push(`${f.split('src')[1]}:${i + 1}`);
      });
    }
    expect(sayi, 'kapsam tabanı (L45)').toBeGreaterThanOrEqual(10);
    expect(ihlal).toEqual([]);
  });

  it('hesap formunda sunucu hatası alert olarak görünür', async () => {
    global.fetch = vi.fn(async (url, opts = {}) => {
      const yol = new URL(url, 'http://localhost').pathname;
      if (yol === '/api/accounts' && opts.method === 'POST') {
        return { ok: false, status: 422, headers: { get: () => 'application/json' },
                 json: async () => ({ detail: 'Ad boş olamaz' }), text: async () => '{"detail":"Ad boş olamaz"}' };
      }
      const govde = bosKullanici[yol];
      return { ok: govde !== undefined, status: govde !== undefined ? 200 : 404,
               headers: { get: () => 'application/json' },
               json: async () => (govde !== undefined ? govde : { detail: 'yok' }), text: async () => '{}' };
    });
    render(<ToastProvider><Accounts /></ToastProvider>);
    fireEvent.click(await screen.findByRole('button', { name: /Yeni Hesap/ }));
    await waitFor(() => expect(screen.getByLabelText('Ad')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Ad'), { target: { value: 'X' } });
    fireEvent.click(screen.getByRole('button', { name: /Kaydet|Oluştur|Ekle/ }));
    const uyari = await screen.findByRole('alert');
    expect(uyari).toHaveTextContent('Ad boş olamaz');
  });
});
