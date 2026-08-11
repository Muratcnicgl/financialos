/**
 * BUG #288 — SERVICE WORKER API YANITLARINI ÖNBELLEĞE ALMAZ.
 *
 * ÖLÇÜLEN DEFEKT (11 Ağu 2026, canlı kullanım): kullanıcı kapalı betada giriş yaptı ve
 * "Backend ile bağlantı yok / Cockpit yüklenemedi" gördü. Konsolda:
 *   `FetchEvent.respondWith received an error: no-response`
 * Backend'in kendisi sağlamdı (`/api/ready`, `/api/meta`, `/api/health` hepsi 200; tünel
 * açıktı). Suçlu service worker'dı.
 *
 * MEKANİZMA: `/api/*` için `NetworkFirst` + `networkTimeoutSeconds: 5`. Beş saniyede yanıt
 * gelmezse Workbox ÖNBELLEĞE düşer; o istek önbellekte YOKSA `no-response` fırlatır ve
 * istek TAMAMEN ölür. Yani zaman aşımı bir yedek değil, ARIZA üretiyordu.
 *
 * 5 sn zaten yanlış bir tavandı: koç ucu iki LLM çağrısı sürer (10-40 sn) ve tünel yolu
 * ek gecikme ekler.
 *
 * TAVANI BÜYÜTMEK ÇÖZÜM DEĞİLDİ: bu bir finans uygulaması, API yanıtları BAKİYE taşıyor.
 * Önbellekten servis edilen bakiye kullanıcıya TAZE görünür — BUG #239'un kapattığı hata.
 * Ayrıca yanıtlar tarayıcı önbelleğinde kalır; aynı cihazı kullanan başkası okuyabilir
 * (BUG #180).
 *
 * KARAR: app shell önbelleğe alınır (uygulama çevrimdışı AÇILIR ve dürüst bir hata
 * gösterir); VERİ asla önbellekten gelmez.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const kok = dirname(fileURLToPath(import.meta.url));
const config = readFileSync(join(kok, '..', 'vite.config.js'), 'utf8');
// Yorum satırlarını at: gerekçe metninde geçen kelimeler kapıyı tetiklemesin (BUG #273 dersi).
const kod = config.split('\n').filter((s) => !s.trim().startsWith('//')).join('\n');

describe('BUG #288 — PWA önbellek sözleşmesi', () => {
  it('API yanıtları için çalışma-anı önbelleği YOK', () => {
    expect(kod).toContain('runtimeCaching: []');
  });

  it('NetworkFirst /api için KULLANILMAZ (no-response üretiyordu)', () => {
    expect(kod).not.toContain('NetworkFirst');
  });

  it('networkTimeoutSeconds hiç yok (zaman aşımı yedek değil, arıza üretiyordu)', () => {
    expect(kod).not.toContain('networkTimeoutSeconds');
  });

  it('api-cache adlı bir önbellek tanımlanmaz (finansal veri tarayıcıda kalmaz)', () => {
    expect(kod).not.toContain('api-cache');
  });

  it('/api navigasyonlarına index.html dönülmez', () => {
    expect(kod).toContain('navigateFallbackDenylist');
  });

  it('app shell precache KORUNUR — uygulama çevrimdışı açılıp dürüst hata göstermeli', () => {
    expect(kod).toContain('globPatterns');
    expect(kod).toContain("navigateFallback: '/index.html'");
  });
});
