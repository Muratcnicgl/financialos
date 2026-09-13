/**
 * DVIZ-010 KAPISI (BUG #455) — SIKIŞMA BANDI.
 *
 * Ölçülen (13 Eyl 2026): bakiye trendinde sıkışma yalnız kırmızı noktaydı; eşik altı bölge
 * gölgelenmiyor, `crunchThreshold` grafiğe hiç ulaşmıyordu. Kilitlenen: `esikBandi` saf
 * fonksiyonu — bakiye eşiğin altına inmiyorsa band YOK (sahte tehlike çizilmez), iniyorsa
 * [enAz, eşik]; Cashflow eşiği geçirir; grafik `ReferenceArea` ve eşik > 0 için çizgi çizer.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { esikBandi } from './components/BalanceTrend.jsx';

describe('DVIZ-010 — sıkışma bandı', () => {
  it('eşik altına inmeyen bakiyede band yok; inende [enAz, eşik]', () => {
    expect(esikBandi([{ balance: 100 }, { balance: 50 }], 0)).toBeNull();
    expect(esikBandi([{ balance: 100 }, { balance: -30 }], 0)).toEqual({ y1: -30, y2: 0 });
    expect(esikBandi([{ balance: 800 }, { balance: 1200 }], 1000)).toEqual({ y1: 800, y2: 1000 });
    expect(esikBandi([], 0)).toBeNull();
  });

  it('Cashflow eşiği geçirir; grafik band ve eşik çizgisi çizer (kaynak bağı)', () => {
    const cf = readFileSync(join(__dirname, 'panels', 'Cashflow.jsx'), 'utf-8');
    expect(cf).toMatch(/<BalanceTrend[^>]*crunchThreshold=\{crunchThreshold\}/);
    const bt = readFileSync(join(__dirname, 'components', 'BalanceTrend.jsx'), 'utf-8');
    expect(bt).toMatch(/<ReferenceArea y1=\{band\.y1\} y2=\{band\.y2\}/);
    expect(bt).toMatch(/crunchThreshold > 0 && \(/);
  });
});
