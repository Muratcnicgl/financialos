/**
 * UX-033 KAPISI (BUG #469) — KOÇ GİRDİSİ YAZDIKÇA BÜYÜR (2→6 SATIR).
 * Kilitlenen: `otoBuyut` yüksekliği scrollHeight'a ayarlar ama azamiyi aşmaz; textarea
 * onChange'de çağrılır, gönderince sıfırlanır; "/" komut menüsü bilinçli yok (öneri çipleri var).
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { otoBuyut, OTO_BUYUT_AZAMI_SATIR } from './panels/Coach.jsx';

describe('UX-033 — otomatik büyüyen girdi', () => {
  it('scrollHeight kadar büyür, azamide durur, null güvenli', () => {
    const el = document.createElement('textarea');
    document.body.appendChild(el);
    el.style.lineHeight = '24px';
    Object.defineProperty(el, 'scrollHeight', { configurable: true, get: () => 60 });
    otoBuyut(el);
    expect(el.style.height).toBe('60px');
    Object.defineProperty(el, 'scrollHeight', { configurable: true, get: () => 900 });
    otoBuyut(el);
    expect(el.style.height).toBe(`${24 * OTO_BUYUT_AZAMI_SATIR + 16}px`);
    expect(() => otoBuyut(null)).not.toThrow();
    expect(OTO_BUYUT_AZAMI_SATIR).toBe(6);
  });

  it('textarea onChange büyütür, gönderince sıfırlanır (kaynak bağı)', () => {
    const src = readFileSync(join(__dirname, 'panels', 'Coach.jsx'), 'utf-8');
    expect(src).toMatch(/onChange=\{\(e\) => \{ setInput\(e\.target\.value\); otoBuyut\(e\.target\); \}\}/);
    expect(src).toMatch(/textareaRef\.current\.style\.height = 'auto'/);
  });
});
