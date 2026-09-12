/**
 * DVIZ-005 KAPISI (BUG #429) — KART ALTINDA "AY BAŞINDAN BERİ" FARKI.
 *
 * Ölçülen (12 Eyl 2026): net değer snapshot geçmişi günlerdir birikiyordu, kokpit kartları
 * yalnız mutlak değer taşıyordu; "kart borcu düştü mü" sorusu Raporlar'daki eğriden
 * okunuyordu. `MetricCard` artık `degisim = { tutar, etiket, azalmaIyi }` alır.
 *
 * Kilitlenen: fark yoksa satır yok (sıfır uydurulmaz); işaret METİNLE taşınır (▲/▼ + +/−),
 * renk yalnız pekiştirir; borç kartında AZALMA iyidir (yeşil), varlıkta artış; 0 nötr.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import MetricCard from './components/MetricCard.jsx';

const satir = () => screen.queryByTestId('metric-degisim');

describe('DVIZ-005 — MetricCard dönem farkı', () => {
  it('degisim verilmezse ya da tutar sayı değilse satır çizilmez', () => {
    const { unmount } = render(<MetricCard title="Nakit" value={10} />);
    expect(satir()).toBeNull();
    unmount();
    render(<MetricCard title="Nakit" value={10} degisim={{ tutar: undefined, etiket: 'x' }} />);
    expect(satir()).toBeNull();
  });

  it('varlık kartı: artış ▲ + "+" ve olumlu renk; etiket satırda', () => {
    render(<MetricCard title="Nakit" value={300} suffix=" ₺" degisim={{ tutar: 200, etiket: 'ay başından beri' }} />);
    const s = satir();
    expect(s).toHaveTextContent('▲');
    expect(s).toHaveTextContent('+200,00 ₺');
    expect(s).toHaveTextContent('ay başından beri');
    expect(s.className).toMatch(/positive/);
  });

  it('borç kartı: azalma ▼ + "−" ama OLUMLU renk (azalmaIyi); artış olumsuz', () => {
    const { unmount } = render(<MetricCard title="Kart Borcu" value={50} suffix=" ₺"
                                           degisim={{ tutar: -30, azalmaIyi: true }} />);
    expect(satir()).toHaveTextContent('▼');
    expect(satir()).toHaveTextContent('−30,00 ₺');
    expect(satir().className).toMatch(/positive/);
    unmount();
    render(<MetricCard title="Kart Borcu" value={50} suffix=" ₺" degisim={{ tutar: 30, azalmaIyi: true }} />);
    expect(satir()).toHaveTextContent('▲');
    expect(satir().className).toMatch(/negative/);
  });

  it('sıfır fark: "=" ve nötr renk, işaret yok', () => {
    render(<MetricCard title="Kredi" value={0} suffix=" ₺" degisim={{ tutar: 0, azalmaIyi: true }} />);
    expect(satir()).toHaveTextContent('=');
    expect(satir().className).toMatch(/zinc/);
    expect(satir().textContent).not.toMatch(/[+−]/);
  });

  it('Cockpit her para kartına degisim bağlar; borç kartlarında azalmaIyi (kaynak bağı)', () => {
    const src = readFileSync(join(__dirname, 'panels', 'Cockpit.jsx'), 'utf-8');
    const bagli = [...src.matchAll(/degisim: degisim\('([a-z_]+)'(, true)?\)/g)]
      .map((m) => [m[1], Boolean(m[2])]);
    const alanlar = new Set(bagli.map(([a]) => a));
    expect([...alanlar].sort()).toEqual(['kart_borcu', 'kredi_borcu', 'nakit_kasa', 'net_deger', 'net_deger_tam', 'yatirim_deger']);
    for (const [alan, azalmaIyi] of bagli) {
      expect(azalmaIyi, alan).toBe(alan.endsWith('_borcu'));
    }
    expect(src).toMatch(/dd\.ay_basi \? 'ay başından beri'/);
  });
});
