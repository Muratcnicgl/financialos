/**
 * FEAT-033 KAPISI (BUG #430) — AYLIK ÖZETTE "GEÇEN AYA GÖRE" ANLATISI VE KATEGORİ KAYMALARI.
 *
 * Ölçülen (12 Eyl 2026): aylık özet kartı gider toplamının yüzde okunu gösteriyordu; hangi
 * kategorinin kaydığını söyleyen satır yoktu. Backend `anlati` + `kategori_kaymalari` verir;
 * kart bunları çizer. Kilitlenen: anlatı metni aynen; kaymalarda işaret METİNLE (+/−), yeni
 * ve kaybolan durumları sözle; anlatı yoksa/kayma yoksa satır yok (eski yanıt şekli de kırmaz).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return { ...gercek, reportsApi: { monthlySummary: vi.fn() } };
});
// eslint-disable-next-line import/first
import MonthlySummary from './components/MonthlySummary.jsx';
// eslint-disable-next-line import/first
import { reportsApi } from './api.js';

const OZET = {
  period: { label: 'Eylül 2026', month: 9, year: 2026 },
  current: { total_income: 1000, total_expense: 2000, net_change: -1000, transaction_count: 3, savings_rate: null,
             expense_categories: [{ category: 'market', total: 1500, count: 1, percentage: 75 }] },
  previous_period: { label: 'Ağustos 2026' },
  trend: { income_delta_pct: null, expense_delta_pct: 25, net_change_delta: -400, prev_net_change: -600 },
};

describe('FEAT-033 — aylık özet anlatısı', () => {
  it('anlatı ve kaymalar çizilir; işaret metinle, durumlar sözle', async () => {
    reportsApi.monthlySummary.mockResolvedValue({
      ...OZET,
      anlati: 'Ayın ilk 12 günü (Ağustos tam ayıyla kıyas, kısmi); gider Ağustos ayına göre %25 arttı; yeni: saglik.',
      kategori_kaymalari: [
        { category: 'market', current: 1500, previous: 1000, delta: 500, delta_pct: 50, durum: 'artti' },
        { category: 'ulasim', current: 0, previous: 400, delta: -400, delta_pct: -100, durum: 'kayboldu' },
        { category: 'saglik', current: 300, previous: 0, delta: 300, delta_pct: null, durum: 'yeni' },
      ],
    });
    render(<MonthlySummary />);
    const anlati = await screen.findByTestId('ay-anlatisi');
    expect(anlati).toHaveTextContent('Ayın ilk 12 günü');
    expect(anlati).toHaveTextContent('%25 arttı');
    const liste = screen.getByTestId('kategori-kaymalari');
    const satirlar = [...liste.querySelectorAll('li')].map((li) => li.textContent);
    expect(satirlar[0]).toMatch(/market\+500,00.*%50/);
    expect(satirlar[1]).toMatch(/ulasim−400,00.*bu ay yok/);
    expect(satirlar[2]).toMatch(/saglik\+300,00.*yeni/);
    expect(satirlar[2]).not.toMatch(/%/);
  });

  it('anlatı ve kayma alanları yoksa (eski yanıt) satır yok, kart yine çizilir', async () => {
    reportsApi.monthlySummary.mockResolvedValue(OZET);
    render(<MonthlySummary />);
    await screen.findByText(/Eylül 2026/);
    expect(screen.queryByTestId('ay-anlatisi')).toBeNull();
    expect(screen.queryByTestId('kategori-kaymalari')).toBeNull();
  });
});
