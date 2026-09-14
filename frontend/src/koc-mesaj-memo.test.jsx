/**
 * PERF-009 / FE-016 / FE-034 (BUG #488): koç mesaj kartı her tuşta yeniden ayrıştırılmaz.
 *
 * Ölçüm (14 Eyl 2026): girdi kutusuna her tuş basışı CoachInner'ı yeniden çizer; `Message`
 * memo değildi, `handleActionResolved` her çizimde yeni kimlik alıyordu → 50 mesajın markdown'ı
 * her tuşta baştan ayrıştırılıyordu. Kilitlenen: geçmişte N koç mesajı varken 5 tuş basışı
 * markdown çizim sayısını ARTIRMAZ; mesaj listesi değişince (yeni mesaj) yalnız yeni kart çizilir.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const cizim = vi.hoisted(() => ({ sayi: 0 }));
vi.mock('react-markdown', () => ({
  default: ({ children }) => { cizim.sayi += 1; return <div data-testid="md">{children}</div>; },
}));

const GECMIS = vi.hoisted(() => Array.from({ length: 5 }, (_, i) => ({
  id: 100 + i, role: i % 2 ? 'user' : 'assistant', content: `mesaj ${i} **kalın**`,
  created_at: '2026-09-14T08:00:00+00:00', actions: [],
})));

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return {
    ...gercek,
    coachApi: {
      history: vi.fn().mockResolvedValue(GECMIS),
      usage: vi.fn().mockResolvedValue(null),
      send: vi.fn(), reset: vi.fn(),
    },
    cockpitApi: { get: vi.fn().mockResolvedValue({ accounts: [] }) },
    userApi: { kvkkDurum: vi.fn().mockResolvedValue({ guncel: true }), me: vi.fn().mockResolvedValue({}) },
  };
});

import Coach from './panels/Coach.jsx';
import { ToastProvider } from './components/Toast.jsx';

beforeEach(() => { cizim.sayi = 0; sessionStorage.clear(); localStorage.clear(); });

describe('BUG #488 — mesaj kartı memo', () => {
  it('5 tuş basışı markdown çizimini artırmaz', async () => {
    render(<ToastProvider><Coach /></ToastProvider>);
    await waitFor(() => expect(screen.getAllByTestId('md').length).toBe(3));   // 3 koç mesajı
    const ilk = cizim.sayi;
    expect(ilk).toBeGreaterThanOrEqual(3);
    const girdi = screen.getByPlaceholderText(/Bir şey sor/);
    for (const h of 'kira?') fireEvent.change(girdi, { target: { value: girdi.value + h } });
    expect(girdi.value).toBe('kira?');
    expect(cizim.sayi).toBe(ilk);
  });
});
