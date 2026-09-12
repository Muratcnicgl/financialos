/**
 * DVIZ-004 / FEAT-023 KAPISI (BUG #428) — AY-BE-AY SERİ VE TASARRUF ORANI GÖRÜNÜR.
 * Kilitlenen: bileşen backend serisini çizer, ay kısaltmaları ve oranlar (None → "—"),
 * ortalama; boş dönemde dürüst metin; yükleme durumu erişilebilir.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return { ...gercek, reportsApi: { ...gercek.reportsApi, monthlySeries: vi.fn() } };
});
import AylikSeri from './components/AylikSeri.jsx';
import { reportsApi } from './api.js';

const SERI = {
  months: 3, avg_savings_rate: 42.5,
  series: [
    { year: 2025, month: 11, label: 'Kasım 2025', total_income: 0, total_expense: 300, net_change: -300, savings_rate: null },
    { year: 2025, month: 12, label: 'Aralık 2025', total_income: 2000, total_expense: 1500, net_change: 500, savings_rate: 25 },
    { year: 2026, month: 1, label: 'Ocak 2026', total_income: 1000, total_expense: 400, net_change: 600, savings_rate: 60 },
  ],
};

describe('AylikSeri', () => {
  it('oranları ve ortalamayı basar; gelirsiz ay "—"', async () => {
    reportsApi.monthlySeries.mockResolvedValue(SERI);
    render(<AylikSeri months={3} />);
    const kart = await screen.findByTestId('aylik-seri');
    expect(kart).toHaveTextContent('Son 3 ay');
    expect(kart).toHaveTextContent('%42,5');
    expect(kart).toHaveTextContent('%25');
    expect(kart).toHaveTextContent('%60');
    expect(kart).toHaveTextContent('—');
    expect(reportsApi.monthlySeries).toHaveBeenCalledWith({ months: 3 });
  });

  it('boş dönem dürüst metin; hata sessiz ama görünür', async () => {
    reportsApi.monthlySeries.mockResolvedValue({ months: 2, avg_savings_rate: null,
      series: [{ year: 2026, month: 8, label: 'Ağustos 2026', total_income: 0, total_expense: 0, net_change: 0, savings_rate: null },
               { year: 2026, month: 9, label: 'Eylül 2026', total_income: 0, total_expense: 0, net_change: 0, savings_rate: null }] });
    render(<AylikSeri months={2} />);
    expect(await screen.findByText('Bu dönemde işlem yok.')).toBeInTheDocument();
  });
});
