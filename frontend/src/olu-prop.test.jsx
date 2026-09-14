/**
 * FE-006 (BUG #482): ölü prop yok — panel-arası tazeleme, yeniden bağlanmanın kendisidir.
 *
 * Ölçüm (14 Eyl 2026): `Coach` bir `onActionResolved` prop'u bekliyor, App hiç geçmiyordu;
 * üç koruma bloğundan biri hiç koşmayan bir çağrıyı koruyordu. App sekmeleri koşullu bağlar,
 * kokpit her geçişte `load()` çağırır — sinyal zaten var. Kilitlenen:
 *  - Coach dış prop almaz (ölü prop geri gelmesin),
 *  - App sekmeleri koşullu bağlar (bu, tazeleme garantisinin kaynağı),
 *  - Cockpit bağlanınca yükler (`useEffect(() => { load(); }, [load])`).
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const oku = (p) => readFileSync(join(__dirname, p), 'utf-8');

describe('FE-006 — ölü prop', () => {
  it('Coach dış prop almaz; App prop geçmez', () => {
    const coach = oku('panels/Coach.jsx');
    expect(coach).toMatch(/export default function Coach\(\) \{/);
    expect(coach).toMatch(/function CoachInner\(\) \{/);
    expect(coach).not.toMatch(/onActionResolved\?\.\(/);
    const app = oku('App.jsx');
    expect(app).toMatch(/activeTab === 'coach' && <Coach \/>/);
  });

  it('sekmeler koşullu bağlanır; kokpit bağlanınca yükler', () => {
    const app = oku('App.jsx');
    expect(app).toMatch(/activeTab === 'cockpit' && <Cockpit setActiveTab=\{setActiveTab\} \/>/);
    const ck = oku('panels/Cockpit.jsx');
    expect(ck).toMatch(/useEffect\(\(\) => \{ load\(\); \}, \[load\]\);/);
  });
});
