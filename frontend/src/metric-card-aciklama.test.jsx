/**
 * UX-021 KAPISI (BUG #423) — "GÖRÜLEN" / "TAM" NET DEĞER AÇIKLAMASI.
 *
 * Ölçülen (12 Eyl 2026): detaylı görünümde iki kart iki farklı sayı gösteriyor, altyazı statik
 * ("Alacaksız (operasyonel)"), farkın ne olduğunu söyleyen yer yoktu. `MetricCard` artık
 * isteğe bağlı `aciklama` alır: "?" düğmesi (aria-expanded/aria-controls, dokunmatikte tap)
 * açıklamayı kartın içinde açar. Kilitlenen: düğme yalnız açıklama varken; açılış/kapanış;
 * Cockpit'te iki net değer kartı açıklama taşır ve alacak sözcüğünü söyler.
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import MetricCard from './components/MetricCard.jsx';

describe('UX-021 — MetricCard açıklaması', () => {
  it('açıklama yoksa düğme yok; varsa tıklayınca açılır ve erişilebilir bağlı', () => {
    const { unmount } = render(<MetricCard title="Reel Bütçe" value={10} />);
    expect(screen.queryByRole('button')).toBeNull();
    unmount();
    render(<MetricCard title="Görülen Net Değer" value={10} aciklama="Görülen = cüzdanında olan." />);
    const dugme = screen.getByRole('button', { name: /Görülen Net Değer: açıklama/ });
    expect(dugme).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('note')).toBeNull();
    fireEvent.click(dugme);
    expect(dugme).toHaveAttribute('aria-expanded', 'true');
    const not = screen.getByRole('note');
    expect(not).toHaveTextContent('cüzdanında olan');
    expect(dugme.getAttribute('aria-controls')).toBe(not.id);
    fireEvent.click(dugme);
    expect(screen.queryByRole('note')).toBeNull();
  });

  it('Cockpit iki net değer kartına açıklama verir (kaynak bağı)', () => {
    const src = readFileSync(join(__dirname, 'panels', 'Cockpit.jsx'), 'utf-8');
    const aciklamalar = [...src.matchAll(/aciklama:\s*(?:netAyrimVar\s*\?\s*)?'([^']+)'/g)].map((m) => m[1]);
    expect(aciklamalar.length).toBeGreaterThanOrEqual(2);
    expect(aciklamalar.join(' ')).toMatch(/alacak/i);
    expect(aciklamalar.join(' ')).toMatch(/Görülen/);
  });
});
