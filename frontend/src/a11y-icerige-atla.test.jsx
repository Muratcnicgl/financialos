/**
 * A11Y-011 KAPISI (BUG #440) — "İÇERİĞE ATLA" BAĞLANTISI.
 *
 * Ölçülen (13 Eyl 2026): odak halkası BUG #433 ile geldi; skip link yoktu — klavye kullanıcısı
 * her sayfada başlık + 13 sekmeyi Tab'la geçiyordu (WCAG 2.4.1). Kilitlenen: gövdedeki İLK
 * odaklanabilir öğe `#panel-icerik`e giden bağlantı; hedef `<main>` var ve `tabIndex=0`
 * (odak alabilir); bağlantı odaksızken ekran-okuyucuya özel (sr-only), odakta görünür.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

describe('A11Y-011 — içeriğe atla', () => {
  const src = readFileSync(join(__dirname, 'App.jsx'), 'utf-8');

  it('skip link kabuğun ilk çocuğu, hedefi main ve odakta görünür', () => {
    const kabuk = src.indexOf('className="h-dvh flex flex-col');
    const baglanti = src.indexOf('href="#panel-icerik"', kabuk);
    const header = src.indexOf('<header', kabuk);
    expect(baglanti).toBeGreaterThan(kabuk);
    expect(baglanti, 'skip link header\'dan ÖNCE olmalı').toBeLessThan(header);
    const blok = src.slice(baglanti, baglanti + 300);
    expect(blok).toMatch(/sr-only focus:not-sr-only/);
    expect(blok).toMatch(/İçeriğe atla/);
    expect(src).toMatch(/<main[^>]*id="panel-icerik"[^>]*tabIndex=\{0\}/s);
  });
});
