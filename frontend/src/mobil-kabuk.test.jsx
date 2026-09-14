/**
 * MOB-009/011/012/017 (BUG #499): mobil kabuk — tema rengi, güvenli alan, dvh yedeği.
 *
 * Ölçüm (14 Eyl 2026): `theme-init.js` localStorage'da `financialos-theme` okuyordu, React
 * tarafı `theme` yazıyordu → açık tema kullanan herkes her açılışta koyu başlayıp React
 * mount'unda açığa dönüyordu (flash). `theme-color` sabit slate #0f172a'ydı (hiçbir zemine
 * uymaz), geçişte güncellenmiyordu; başlık/gövde çentik güvenli alanı almıyordu; `h-dvh`
 * eski Safari'de yedeksizdi. Kilitlenen:
 *  - theme-init: `theme` anahtarı, yoksa OS tercihi; meta'yı yazar (jsdom'da gerçekten çalıştırılır),
 *  - App geçişte meta'yı günceller; index.html başlangıç değeri zinc-950,
 *  - index.css güvenli alan sınıfları + `@supports not (height: 100dvh)` yedeği; App bunları takar.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { TEMA_RENGI } from './lib/tema.js';

const oku = (p) => readFileSync(join(__dirname, '..', p), 'utf-8');

function temaInitKostur() {
  // IIFE betiğini jsdom'da olduğu gibi çalıştır (module değil, klasik script)
  const kaynak = oku('public/theme-init.js');
  // Betik klasik <script>; test onu tarayıcı gibi koşturur (Function ile).
  new Function(kaynak)();
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove('dark');
  document.head.innerHTML = '<meta name="theme-color" content="#000000">';
});

describe('BUG #499 — theme-init', () => {
  it('kayıt light → dark sınıfı yok, meta açık zemin', () => {
    localStorage.setItem('theme', 'light');
    temaInitKostur();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.querySelector('meta[name="theme-color"]').getAttribute('content')).toBe('#fafafa');
  });

  it('kayıt dark → dark sınıfı ve koyu meta; kayıt yoksa OS tercihi okunur', () => {
    localStorage.setItem('theme', 'dark');
    temaInitKostur();
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.querySelector('meta[name="theme-color"]').getAttribute('content')).toBe('#09090b');
    localStorage.clear();
    document.documentElement.classList.remove('dark');
    window.matchMedia = (q) => ({ matches: q.includes('light'), media: q, addEventListener() {}, removeEventListener() {} });
    temaInitKostur();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('eski anahtar (financialos-theme) artık okunmuyor', () => {
    expect(oku('public/theme-init.js')).not.toContain('financialos-theme');
  });
});

describe('BUG #499 — kaynak bağı', () => {
  it('App geçişte meta günceller; index.html başlangıcı zinc-950', () => {
    const app = oku('src/App.jsx');
    expect(app).toMatch(/meta\[name="theme-color"\]'\)\?\.setAttribute\('content', TEMA_RENGI\[theme\]\)/);
    // theme-init.js import edemez: iki değer kopya, tek gerçek — burada karşılaştırılır
    const init = oku('public/theme-init.js');
    expect(init).toContain(`'${TEMA_RENGI.dark}'`);
    expect(init).toContain(`'${TEMA_RENGI.light}'`);
    expect(oku('index.html')).toContain('<meta name="theme-color" content="#09090b" />');
    expect(oku('index.html')).toContain('viewport-fit=cover');
  });

  it('güvenli alan sınıfları ve dvh yedeği tanımlı ve takılı', () => {
    const css = oku('src/index.css');
    expect(css).toMatch(/header\.guvenli-alan-ust \{ padding-top: env\(safe-area-inset-top, 0px\); \}/);
    expect(css).toMatch(/\.guvenli-alan-yan \{ padding-left: env\(safe-area-inset-left, 0px\); padding-right: env\(safe-area-inset-right, 0px\); \}/);
    expect(css).toMatch(/@supports not \(height: 100dvh\) \{\s*\.h-dvh \{ height: 100vh; \}/);
    const app = oku('src/App.jsx');
    expect(app).toMatch(/<header className="guvenli-alan-ust /);
    expect(app).toMatch(/className="h-dvh guvenli-alan-yan /);
  });
});
