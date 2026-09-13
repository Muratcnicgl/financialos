/**
 * DVIZ-002 KAPISI (BUG #456) — KATEGORİK PALET RENK KÖRÜ GÜVENLİ.
 *
 * Ölçülen (13 Eyl 2026): eski 10'lu palette deutan altında orange-600 ↔ amber-600 ΔE 2,1,
 * protan altında indigo ↔ purple 3,2 — ayırt edilemez. Bu kapı Machado (2009) protan/deutan
 * matrisleriyle simüle edip CIE76 ΔE ölçer: her ikili ≥ 12 (belirgin fark), üç görüşte.
 * Ayrıca her renk iki tema zemininde ≥ 3:1 (modülün eski değişmezi) ve donut en fazla
 * KATEGORIK_TAVAN dilim + "Diğer".
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { KATEGORIK, KATEGORIK_TAVAN } from './lib/grafikRenkleri.js';

const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const lum = (h) => { const [r, g, b] = rgb(h).map(lin); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const cr = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
const PROTAN = [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]];
const DEUTAN = [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]];
const NORMAL = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
const sim = (h, M) => { const l = rgb(h).map(lin); return M.map((row) => Math.min(1, Math.max(0, row[0] * l[0] + row[1] * l[1] + row[2] * l[2]))); };
const lab = ([r, g, b]) => {
  const X = 0.4124 * r + 0.3576 * g + 0.1805 * b, Y = 0.2126 * r + 0.7152 * g + 0.0722 * b, Z = 0.0193 * r + 0.1192 * g + 0.9505 * b;
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  const fx = f(X / 0.95047), fy = f(Y), fz = f(Z / 1.08883);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
};
const de = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const minDe = (pal, M) => {
  const L = pal.map((h) => lab(sim(h, M)));
  let m = Infinity;
  for (let i = 0; i < L.length; i++) for (let j = i + 1; j < L.length; j++) m = Math.min(m, de(L[i], L[j]));
  return m;
};

describe('DVIZ-002 — renk körü güvenli palet', () => {
  it('normal/protan/deutan görüşte her ikili ΔE ≥ 12', () => {
    for (const [ad, M] of [['normal', NORMAL], ['protan', PROTAN], ['deutan', DEUTAN]]) {
      expect(minDe(KATEGORIK, M), ad).toBeGreaterThanOrEqual(12);
    }
  });

  it('her renk iki tema zemininde ≥ 3:1; palet 6 ve tavan onunla aynı', () => {
    for (const h of KATEGORIK) {
      expect(cr(h, '#ffffff'), h).toBeGreaterThanOrEqual(3);
      expect(cr(h, '#18181b'), h).toBeGreaterThanOrEqual(3);
    }
    expect(KATEGORIK.length).toBe(6);
    expect(KATEGORIK_TAVAN).toBe(KATEGORIK.length);
  });

  it('donut tavanı aşan kategorileri "Diğer"de toplar; çubuk tek renk (kaynak bağı)', () => {
    const src = readFileSync(join(__dirname, 'panels', 'Reports.jsx'), 'utf-8');
    expect(src).toMatch(/items\.length > KATEGORIK_TAVAN/);
    expect(src).toMatch(/category: `Diğer \(/);
    expect(src).toMatch(/data=\{dilimler\}/);
    expect(src).toMatch(/<Cell key=\{i\} fill=\{COLORS\[0\]\} \/>/);
  });
});
