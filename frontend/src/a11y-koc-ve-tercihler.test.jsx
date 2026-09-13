/**
 * A11Y-020 + A11Y-016 KAPISI (BUG #450) — KOÇ MESAJI DUYURULUR; SİSTEM TERCİHLERİ DİNLENİR.
 *
 * Ölçülen (13 Eyl 2026): `aria-live` Coach.jsx'te 0 — yeni koç mesajı ekran okuyucuya
 * duyurulmuyordu; "yazıyor" göstergesi üç noktaydı (görsel-only). Tema ilk değeri sabit
 * 'dark' (prefers-color-scheme okunmuyordu); `prefers-reduced-motion` hiç yoktu.
 *
 * Kilitlenen: sohbet listesi role=log + aria-live=polite; yazıyor göstergesi role=status +
 * metin; ilk tema kaydedilmiş tercih yoksa OS tercihinden (light → light), kaydedilmiş tercih
 * kazanır; index.css'te reduced-motion bloğu animasyon/geçişi kısar.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const KOK = join(__dirname);

describe('A11Y-020 — koç sohbeti canlı bölge', () => {
  it('kaynak: liste role=log/aria-live, gösterge role=status + metin', () => {
    const src = readFileSync(join(KOK, 'panels', 'Coach.jsx'), 'utf-8');
    expect(src).toMatch(/role="log" aria-live="polite"/);
    const i = src.indexOf('function CoachTypingIndicator');
    const blok = src.slice(i, i + 400);
    expect(blok).toMatch(/role="status"/);
    expect(blok).toMatch(/Koç yanıt yazıyor/);
  });
});

describe('A11Y-016 — sistem tercihleri', () => {
  it('kayıtlı tema yoksa OS "light" tercihi ilk değer olur; kayıtlı tercih kazanır', async () => {
    const src = readFileSync(join(KOK, 'App.jsx'), 'utf-8');
    expect(src).toMatch(/prefers-color-scheme: light/);
    // davranış: useState başlatıcısını App'ten çıkarmak yerine aynı mantığı kaynaktan doğrula
    const i = src.indexOf("localStorage.getItem('theme')");
    const blok = src.slice(i, i + 400);
    expect(blok.indexOf("return saved")).toBeLessThan(blok.indexOf('prefers-color-scheme'));
  });

  it('index.css hareket azaltma tercihini uygular', () => {
    const css = readFileSync(join(KOK, 'index.css'), 'utf-8');
    const i = css.indexOf('@media (prefers-reduced-motion: reduce)');
    expect(i).toBeGreaterThanOrEqual(0);
    const blok = css.slice(i, i + 400);
    expect(blok).toMatch(/animation-duration: 0\.01ms !important/);
    expect(blok).toMatch(/transition-duration: 0\.01ms !important/);
  });
});
