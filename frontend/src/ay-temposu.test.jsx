/**
 * UX-028 KAPISI (BUG #466) — AY TEMPOSU GÖSTERİMİ.
 * Kilitlenen: hüküm cümlesi durumlara göre (erken/bilinmiyor/üstünde/hedefte); ilerleme çubuğu
 * progressbar rolüyle; Cockpit "bugün" bloğunda bağlı; tempo yoksa hiç çizilmez.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import AyTemposu, { tempoCumlesi } from './components/AyTemposu.jsx';

const T = { gun: 13, ay_gunu: 30, ilerleme_pct: 43.3, harcanan: 1300, projeksiyon: 3000, referans: 2000, referans_ay: 'Ağustos', durum: 'ustunde' };

describe('UX-028 — ay temposu', () => {
  it('cümle durumlara göre', () => {
    expect(tempoCumlesi({ ...T, durum: 'erken', gun: 2 })).toMatch(/henüz erken/);
    expect(tempoCumlesi({ ...T, durum: 'bilinmiyor', referans: null })).toMatch(/referansı yok/);
    expect(tempoCumlesi(T)).toMatch(/Ağustos .* temposunun üstünde/);
    expect(tempoCumlesi({ ...T, durum: 'hedefte' })).toMatch(/temposunun hedefte/);
    expect(tempoCumlesi(null)).toBeNull();
  });

  it('çubuk progressbar; üstündeyken uyarı rengi + ▲; tempo yoksa çizilmez', () => {
    const { unmount } = render(<AyTemposu tempo={T} />);
    const bar = screen.getByRole('progressbar', { name: 'Ay ilerlemesi' });
    expect(bar).toHaveAttribute('aria-valuenow', '43');
    expect(screen.getByTestId('ay-temposu').textContent).toMatch(/▲/);
    unmount();
    render(<AyTemposu tempo={null} />);
    expect(screen.queryByTestId('ay-temposu')).toBeNull();
    const src = readFileSync(join(__dirname, 'panels', 'Cockpit.jsx'), 'utf-8');
    expect(src).toMatch(/<AyTemposu tempo=\{data\.ay_temposu\} \/>/);
  });
});
