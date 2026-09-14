/**
 * MOB-025 (BUG #502): API kök adresi tek kaynak — istemci ayrı bir host'a taşınabilir.
 *
 * Ölçüm (14 Eyl 2026): beş yerde çıplak `fetch('/api/...')` vardı (api.js ×4, SistemDurumu ×1);
 * RN/ayrı host için hepsini elle değiştirmek gerekirdi. Kilitlenen: `apiUrl()` boş BASE'de
 * yolu aynen bırakır (web/proxy korunur), BASE varken mutlak adres kurar (sondaki / kırpılır);
 * üründe `apiUrl` dışında `/api` ile başlayan çıplak fetch yok.
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { apiUrl, apiUrlIle, API_BASE } from './api.js';

function dosyalar(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) dosyalar(yol, out);
    else if (/\.(jsx?|js)$/.test(ad) && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

describe('MOB-025 — API kök adresi', () => {
  it('web: BASE boş, yol aynen', () => {
    expect(API_BASE).toBe('');
    expect(apiUrl('/api/cockpit')).toBe('/api/cockpit');
  });

  it('BASE varken mutlak adres; sondaki / kırpılır; eğik çizgisiz yol düzeltilir', () => {
    expect(apiUrlIle('https://h.example/', '/api/x')).toBe('https://h.example/api/x');
    expect(apiUrlIle('https://h.example', 'api/x')).toBe('https://h.example/api/x');
    expect(apiUrlIle('', '/api/x')).toBe('/api/x');
  });

  it('üründe apiUrl dışında çıplak /api fetch yok', () => {
    const kacaklar = [];
    for (const f of dosyalar(__dirname)) {
      const s = readFileSync(f, 'utf-8');
      for (const m of s.matchAll(/fetch\(\s*[`'"]\/api/g)) kacaklar.push(`${f.split('src')[1]}:${s.slice(0, m.index).split('\n').length}`);
    }
    expect(kacaklar).toEqual([]);
    // request() de apiUrl'den geçer
    expect(readFileSync(join(__dirname, 'api.js'), 'utf-8')).toMatch(/res = await fetch\(apiUrl\(url\), init\)/);
  });
});
