/**
 * UX-035 (BUG #480): başarı anları kutlanır — ölçülü.
 *
 * Ölçüm (14 Eyl 2026): backend borç kilometre taşını üretiyordu (FEAT-017 `borc_ilerleme`
 * › `yeni_milestone`) ama sinyal yalnız koç prompt'una gidiyordu; arayüz sessizdi. Hedef
 * `achieved` olunca düz rozet. Kilitlenen:
 *  - kilometre taşı → kokpitte pankart (role=status) + TEK SEFER konfeti (localStorage),
 *  - hareket azaltma tercihinde konfeti HİÇ çizilmez (A11Y-016 ile tutarlı),
 *  - taze geçiş yoksa pankart yok (kutlama üretilmez),
 *  - hedef achieved geçişi bir kez toast'lanır (kaynak bağı).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import Kutlama, { KONFETI_SURESI_MS } from './components/Kutlama.jsx';
import { borcKutlamasi, hedefKutlamasi, kutlandiMi, KUTLAMA_ONEKI } from './lib/kutlama.js';

const BI = { yeni_milestone: 25, odendi: 45000, guncel_borc: 135000, baslangic_tarih: '2026-06-01' };

function hareket(azalt) {
  window.matchMedia = vi.fn().mockImplementation((q) => ({
    matches: azalt && q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {},
  }));
}

beforeEach(() => { localStorage.clear(); hareket(false); vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); });

describe('UX-035 — kutlama metinleri', () => {
  it('taze kilometre taşı → başlık + ödenen/kalan; geçiş yoksa null', () => {
    const k = borcKutlamasi(BI);
    expect(k.baslik).toBe('🏆 Borcunu %25 azalttın');
    expect(k.detay).toMatch(/45\.000.*ödendi.*135\.000/);
    expect(k.anahtar).toBe('borc_25_2026-06-01');
    expect(borcKutlamasi({ ...BI, yeni_milestone: null })).toBeNull();
    expect(borcKutlamasi(null)).toBeNull();
  });

  it('hedef: yalnız achieved GEÇİŞİ kutlanır', () => {
    const h = { id: 3, title: 'Acil fon', status: 'achieved', goal_type: 'cash_target', target_amount: 50000 };
    expect(hedefKutlamasi({ status: 'active' }, h).baslik).toBe('🎉 Hedef tamamlandı: Acil fon');
    expect(hedefKutlamasi(undefined, h)).not.toBeNull();          // ilk yükleme: önceki yok
    expect(hedefKutlamasi({ status: 'achieved' }, h)).toBeNull();  // zaten tamamdı
    expect(hedefKutlamasi({ status: 'active' }, { ...h, status: 'active' })).toBeNull();
  });
});

describe('UX-035 — Kutlama bileşeni', () => {
  it('pankart role=status; konfeti tek sefer ve 1,8 sn sonra kalkar', () => {
    const k = borcKutlamasi(BI);
    const { unmount } = render(<Kutlama kutlama={k} />);
    expect(screen.getByRole('status')).toHaveTextContent('Borcunu %25 azalttın');
    expect(screen.getByTestId('konfeti').querySelectorAll('.kutlama-parca').length).toBe(14);
    expect(kutlandiMi(k.anahtar)).toBe(true);
    act(() => { vi.advanceTimersByTime(KONFETI_SURESI_MS + 10); });
    expect(screen.queryByTestId('konfeti')).toBeNull();
    unmount();
    // ikinci açılış: pankart kalır, konfeti tekrar etmez
    render(<Kutlama kutlama={k} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByTestId('konfeti')).toBeNull();
    expect(localStorage.getItem(KUTLAMA_ONEKI + k.anahtar)).toBe('1');
  });

  it('hareket azaltma tercihinde konfeti hiç çizilmez, pankart kalır', () => {
    hareket(true);
    render(<Kutlama kutlama={borcKutlamasi(BI)} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByTestId('konfeti')).toBeNull();
  });

  it('kutlama yoksa hiçbir şey çizmez', () => {
    const { container } = render(<Kutlama kutlama={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('UX-035 — kaynak bağı', () => {
  it('kokpit sinyali okur; hedefler geçişi bir kez toast\'lar; CSS parça animasyonu var', () => {
    const ck = readFileSync(join(__dirname, 'panels', 'Cockpit.jsx'), 'utf-8');
    expect(ck).toMatch(/const borcKutlama = borcKutlamasi\(data\.borc_ilerleme\)/);
    expect(ck).toMatch(/\{borcKutlama && <Kutlama key=\{borcKutlama\.anahtar\} kutlama=\{borcKutlama\} \/>\}/);
    const gj = readFileSync(join(__dirname, 'panels', 'Goals.jsx'), 'utf-8');
    expect(gj).toMatch(/hedefKutlamasi\(oncekiHedefler\.current\.find/);
    expect(gj).toMatch(/if \(k && !kutlandiMi\(k\.anahtar\)\) \{\s*kutlandi\(k\.anahtar\);/);
    const css = readFileSync(join(__dirname, 'index.css'), 'utf-8');
    expect(css).toMatch(/@keyframes kutlama-dus/);
    expect(css).toMatch(/\.kutlama-parca \{[\s\S]*animation: kutlama-dus 1\.8s/);
  });
});
