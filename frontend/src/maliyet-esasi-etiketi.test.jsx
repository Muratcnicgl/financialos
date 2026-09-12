/**
 * RULE-007 KAPISI (BUG #437) — MALİYET ESASI "AĞIRLIKLI ORTALAMA" DİYE ETİKETLİ.
 *
 * Ölçülen (13 Eyl 2026): ürün kodunda "FIFO" iddiası yok (0 eşleşme) ama etiket "Maliyet/lot"
 * hangi esas olduğunu söylemiyordu; kâr/stopaj tahmini ağırlıklı ortalamayla hesaplanır
 * (ADR-015), aracı kurum FIFO uygular → farklı fiyatlı lotlarda tahmin sapar. Lot defteri
 * (gerçek FIFO) ADR-019 Wave-3 işidir; bugün doğru olan, esası SÖYLEMEKTİR.
 *
 * Kilitlenen: görünüm ve form etiketi "Ort. maliyet/lot"; form ipucu ağırlıklı ortalama +
 * "FIFO değil" der ve girdiye aria-describedby ile bağlıdır; hiçbir ürün dosyası FIFO vaat etmez.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const KOK = join(__dirname);
function urunDosyalari(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) { if (ad !== '__fixtures__') urunDosyalari(yol, out); }
    else if (/\.(jsx?|css)$/.test(ad) && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

describe('RULE-007 — maliyet esası etiketi', () => {
  const src = readFileSync(join(KOK, 'panels', 'Accounts.jsx'), 'utf-8');

  it('görünüm ve form "Ort. maliyet/lot" der; ipucu ağırlıklı ortalama ve FIFO-değil söyler', () => {
    expect((src.match(/Ort\. maliyet\/lot/g) || []).length).toBeGreaterThanOrEqual(2);
    expect(src).not.toMatch(/>Maliyet\/lot</);
    expect(src).toMatch(/id="maliyet-ipucu"/);
    expect(src).toMatch(/aria-describedby="maliyet-ipucu"/);
    const i = src.indexOf('id="maliyet-ipucu"');
    const ipucu = src.slice(i, i + 300);
    expect(ipucu).toMatch(/ağırlıklı ortalama/i);
    expect(ipucu).toMatch(/FIFO değil/);
  });

  it('ürün kodu FIFO vaat etmez (yalnız "değil" bağlamında geçer)', () => {
    const ihlal = [];
    for (const f of urunDosyalari(KOK)) {
      const metin = readFileSync(f, 'utf-8');
      for (const m of metin.matchAll(/FIFO/g)) {
        const pencere = metin.slice(m.index, m.index + 12);
        if (!/FIFO değil/.test(pencere)) ihlal.push(`${f.split('src')[1]}@${m.index}`);
      }
    }
    expect(ihlal).toEqual([]);
  });
});
