/**
 * PERF-005/006 + FE-009 (BUG #486): kod bölme — ilk boyaya yalnız kokpit ve çekirdek biner.
 *
 * Ölçüm (14 Eyl 2026, `npm run build`): ÖNCE tek parça 1.113 kB JS (13 panel + recharts);
 * SONRA ilk yük ≈ index 183 + react 133 + lucide 27 kB, recharts 443 kB ayrı parçada ve
 * `modulepreload` listesinde YOK (kokpitteki tek tüketici `AylikSeri` tembel). Kilitlenen:
 *  - kokpit statik (ilk ekran), diğer 11 panel `lazy()`; `Suspense` sarmalı,
 *  - vite `manualChunks` recharts/react/lucide'ı ayırır,
 *  - kokpit recharts'ı tembel yükler,
 *  - altbilgi sabit "v0.1.0" değil, /api/meta'dan.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const oku = (p) => readFileSync(join(__dirname, p), 'utf-8');

describe('BUG #486 — kod bölme', () => {
  it('kokpit statik, 11 panel tembel, Suspense sarmalı', () => {
    const app = oku('App.jsx');
    expect(app).toMatch(/^import Cockpit from '\.\/panels\/Cockpit\.jsx';/m);
    const tembel = [...app.matchAll(/const (\w+) = lazy\(\(\) => import\('\.\/panels\/(\w+)\.jsx'\)\);/g)].map((m) => m[2]);
    expect(tembel.sort()).toEqual(['Accounts', 'Budget', 'Cashflow', 'Coach', 'DebtStrategy', 'Goals', 'Hesap', 'IncomeDebt', 'RedLines', 'Reports', 'Transactions']);
    expect(app).not.toMatch(/^import (Coach|Reports|Cashflow) from '\.\/panels/m);
    expect(app).toMatch(/<Suspense fallback=\{<PanelYukleniyor \/>\}>[\s\S]*activeTab === 'hesap' && <Hesap \/>[\s\S]*<\/Suspense>/);
  });

  it('satıcı parçaları ayrı; kokpit recharts\'ı tembel yükler', () => {
    const vite = readFileSync(join(__dirname, '..', 'vite.config.js'), 'utf-8');
    expect(vite).toMatch(/manualChunks\(id\)/);
    for (const parca of ["'recharts'", "'react'", "'lucide'"]) expect(vite).toContain(`return ${parca}`);
    const ck = oku('panels/Cockpit.jsx');
    expect(ck).toMatch(/const AylikSeri = lazy\(\(\) => import\('\.\.\/components\/AylikSeri\.jsx'\)\);/);
    expect(ck).not.toMatch(/^import .* from 'recharts'/m);
  });

  it('altbilgi sürümü sabit değil', () => {
    const app = oku('App.jsx');
    expect(app).not.toMatch(/FinancialOS · v\d/);
    expect(app).toMatch(/FinancialOS\{surumMetni\}/);
    expect(app).toMatch(/metaApi\.get\(\)\)\.then\(\(m\) => \{[\s\S]*m\?\.surum/);
  });
});
