/**
 * TEST-034 KAPISI (BUG #419) — BACKEND ŞEMASI ↔ FRONTEND BEKLENTİSİ TEK SÖZLEŞME.
 *
 * Ölçülen (12 Eyl 2026): kokpit yanıtının anahtarları backend'de `__fixtures__/bos-kullanici.json`
 * ile donduruluyor (BUG #304 sınıfı fixture kapısı, `test_bos_durum_frontend_fixture`; kod değişince `FOS_FIXTURE_UPDATE=1` ile yenilenir);
 * `Cockpit.jsx` 37 `data.<anahtar>` okuyor ve iki taraf birbirini görmüyordu — backend bir
 * alanı yeniden adlandırsa panel sessizce `undefined` basardı.
 *
 * Kilitlenen: Cockpit.jsx'in okuduğu her `data.<anahtar>` fixture'daki `/api/cockpit`
 * gövdesinde var. Sözleşme tek yerde (fixture), iki taraf ona bakar.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const KOK = join(__dirname);

describe('TEST-034 — kokpit sözleşmesi', () => {
  it('Cockpit.jsx\'in okuduğu her anahtar backend fixture\'ında var', () => {
    const fixture = JSON.parse(readFileSync(join(KOK, '__fixtures__', 'bos-kullanici.json'), 'utf-8'));
    const kokpit = fixture['/api/cockpit'];
    expect(kokpit && typeof kokpit === 'object').toBe(true);
    const backend = new Set(Object.keys(kokpit));
    const src = readFileSync(join(KOK, 'panels', 'Cockpit.jsx'), 'utf-8');
    const okunan = new Set([...src.matchAll(/\bdata\.([a-z_][a-z0-9_]*)/g)].map((m) => m[1]));
    expect(okunan.size, 'kapsam tabanı (L45)').toBeGreaterThanOrEqual(30);
    const eksik = [...okunan].filter((k) => !backend.has(k)).sort();
    expect(eksik, `Cockpit.jsx backend'de olmayan alan okuyor: ${eksik.join(', ')}`).toEqual([]);
  });
});
