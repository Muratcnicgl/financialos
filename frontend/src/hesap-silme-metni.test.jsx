/**
 * UX-030 KAPISI (BUG #434) — HESAP SİLME METNİ SUNUCUNUN GERÇEK DAVRANIŞINI SÖYLER.
 *
 * Ölçülen (12 Eyl 2026): onay penceresi "Bu hesap ve bağlı işlemler silinecek" diyordu;
 * sunucu bağlı kayıt varsa silmeyi REDDEDER (409, sayılarıyla — `test_hesap_silme_reddi_kapisi`).
 * Yani metin olmayan bir kaskadla korkutuyor, sonra 409 geliyordu. Kilitlenen: kaskad iddiası
 * yok; "silinmez" ve sayı vaadi var; üst bileşenin hatası pencereye de düşer (throw).
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

describe('UX-030 — hesap silme metni', () => {
  const src = readFileSync(join(__dirname, 'panels', 'Accounts.jsx'), 'utf-8');
  const i = src.indexOf('function ConfirmDeleteModal');
  const modal = src.slice(i);

  it('kaskad iddiası yok; reddin sebebi ve sayı vaadi var', () => {
    expect(i).toBeGreaterThanOrEqual(0);
    expect(modal).not.toMatch(/bağlı işlemler silinecek/);
    expect(modal).toMatch(/silinmez/);
    expect(modal).toMatch(/kaç kayıt bağlı/);
  });

  it('üst handleDelete hatayı yutmaz — pencere 409 sebebini gösterebilsin', () => {
    const j = src.indexOf('const handleDelete = async (id)');
    const blok = src.slice(j, src.indexOf('};', j));
    expect(blok).toMatch(/throw e/);
  });
});
