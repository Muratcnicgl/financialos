/**
 * A11Y-008 KAPISI (BUG #448) — HER <label> BİR GİRDİYE BAĞLI.
 *
 * Ölçülen (13 Eyl 2026): 99 form kontrolü, 70 `<label>`, `htmlFor` yalnız 2 (BUG #403 slider) —
 * etiketler girdinin YANINDA duruyordu ama ona BAĞLI değildi: ekran okuyucu alanı
 * adlandıramıyor, etikete tıklamak odaklamıyordu (WCAG 1.3.1 / 3.3.2). Düzeltme: bileşen başına
 * `useId` + `htmlFor`/`id` (statik id çoklu örnekte çakışırdı); düğme grupları `role="group"`
 * + `aria-labelledby`.
 *
 * Kilitlenen: kaynakta `htmlFor`suz her `<label>` bir kontrolü SARMALAR (örtük bağ); davranış:
 * hesap formu modalında `getByLabelText` girdiyi bulur (bağ gerçekten kurulu).
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

describe('A11Y-008 — etiket↔girdi bağı', () => {
  it('htmlFor\'suz her <label> bir kontrolü sarmalar', () => {
    const ihlal = [];
    let sayi = 0;
    for (const f of jsxDosyalari(KOK)) {
      const L = readFileSync(f, 'utf-8').split('\n');
      L.forEach((s, i) => {
        if (!/<label\b/.test(s)) return;
        sayi += 1;
        if (/htmlFor=/.test(s)) return;
        const blok = L.slice(i, i + 12).join('\n').split('</label>')[0];
        if (!/<(input|select|textarea)\b/.test(blok)) ihlal.push(`${f.split('src')[1]}:${i + 1}`);
      });
    }
    expect(sayi, 'kapsam tabanı (L45)').toBeGreaterThanOrEqual(60);
    expect(ihlal, 'bağsız etiket').toEqual([]);
  });

  it('hesap formunda etiket metniyle girdi bulunur (bağ kurulu)', async () => {
    global.fetch = vi.fn(async (url) => {
      const yol = new URL(url, 'http://localhost').pathname;
      const govde = bosKullanici[yol];
      return { ok: govde !== undefined, status: govde !== undefined ? 200 : 404,
               headers: { get: () => 'application/json' },
               json: async () => (govde !== undefined ? govde : { detail: 'yok' }),
               text: async () => JSON.stringify(govde ?? {}) };
    });
    render(<ToastProvider><Accounts /></ToastProvider>);
    fireEvent.click(await screen.findByRole('button', { name: /Yeni Hesap/ }));
    await waitFor(() => expect(screen.getByLabelText('Ad')).toBeInTheDocument());
    const ad = screen.getByLabelText('Ad');
    expect(ad.tagName).toBe('INPUT');
    expect(screen.getByLabelText('Tip').tagName).toBe('SELECT');
  });
});
