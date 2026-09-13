/**
 * UX-014 KAPISI (BUG #461) — SIFIRLAMA ONAYI UYGULAMA İÇİ MODAL.
 *
 * Ölçülen (13 Eyl 2026): "Yeni sohbet" `window.confirm` kullanıyordu — tarayıcı diyaloğu,
 * odak/erişilebilirlik kontrolü yok, stil dışı. Şimdi ortak `Modal` (BUG #395: odak tuzağı,
 * Escape, aria-modal). Kilitlenen: kaynakta `window.confirm(` yok; silinecekler listesi ve
 * "geri alınamaz" uyarısı sabitlerden (backend gate aynı sabitleri okur); Modal içinde
 * "Evet, sıfırla" / "Vazgeç".
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

describe('UX-014 — sıfırlama modalı', () => {
  it('window.confirm yok; Modal + sabitler + iki düğme', () => {
    const src = readFileSync(join(__dirname, 'panels', 'Coach.jsx'), 'utf-8');
    expect(src).not.toMatch(/window\.confirm\(/);
    expect(src).toMatch(/const SIFIRLAMA_UYARI = 'Bu işlem geri alınamaz/);
    expect(src).toMatch(/const SIFIRLAMA_SILINECEKLER = \[/);
    const i = src.indexOf('<Modal title="Sohbeti sıfırla"');
    expect(i).toBeGreaterThan(0);
    const blok = src.slice(i, i + 900);
    expect(blok).toMatch(/\{SIFIRLAMA_UYARI\}/);
    expect(blok).toMatch(/SIFIRLAMA_SILINECEKLER\.map/);
    expect(blok).toMatch(/Evet, sıfırla/);
    expect(blok).toMatch(/Vazgeç/);
  });
});
