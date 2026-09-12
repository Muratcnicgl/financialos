/**
 * SEC-027 / BUG #436 KAPISI — GİRİŞ KAPISI GERÇEKTEN ÇALIŞIR.
 *
 * Ölçülen (12 Eyl 2026): `AuthGate` var olmayan `healthApi.get`i çağırıyordu → her açılışta
 * TypeError → catch → 'app' → ilk istek 401 → 'fos:auth-expired' → giriş. Yani kapı hiç
 * çalışmıyor, giriş ekranına 401 dalgasıyla düşülüyordu. Kimlik-gerekli bilgisi artık
 * `/api/meta.kimlik_gerekli` (canlılık ucu sürüm/kimlik bilgisi yayınlamaz).
 *
 * Kilitlenen: kimlik gerekli + token yok → Login (tek meta çağrısıyla, 401 dalgasız);
 * kimlik gerekmiyor → uygulama; kaynakta `healthApi.get` yok.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return {
    ...gercek,
    metaApi: { get: vi.fn(), durum: vi.fn().mockResolvedValue({ saglikli: true }) },
    authApi: { ...gercek.authApi, isLoggedIn: vi.fn(() => false), logout: vi.fn() },
    healthApi: { check: vi.fn().mockResolvedValue({ status: 'ok' }) },
    consumeOAuthRedirect: vi.fn().mockResolvedValue({ status: 'none' }),
    getResetTokenFromUrl: () => null,
    getJoinTokenFromUrl: () => null,
  };
});
vi.mock('./panels/Login.jsx', () => ({ default: () => <div data-testid="giris-ekrani">giriş</div> }));
vi.mock('./panels/Cockpit.jsx', () => ({ default: () => <div data-testid="kokpit">kokpit</div> }));

// eslint-disable-next-line import/first
import App from './App.jsx';
// eslint-disable-next-line import/first
import { metaApi } from './api.js';

beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); });

describe('SEC-027 — giriş kapısı', () => {
  it('kimlik gerekli + token yok → giriş ekranı, tek meta çağrısıyla', async () => {
    metaApi.get.mockResolvedValue({ kimlik_gerekli: true, kayit_modu: 'invite_only' });
    render(<App />);
    expect(await screen.findByTestId('giris-ekrani')).toBeInTheDocument();
    expect(metaApi.get).toHaveBeenCalledTimes(1);
  });

  it('kimlik gerekmiyorsa uygulama açılır', async () => {
    metaApi.get.mockResolvedValue({ kimlik_gerekli: false, kayit_modu: 'open' });
    render(<App />);
    expect(await screen.findByTestId('kokpit')).toBeInTheDocument();
    expect(screen.queryByTestId('giris-ekrani')).toBeNull();
  });

  it('kaynakta var olmayan healthApi.get çağrısı yok', () => {
    const src = readFileSync(join(__dirname, 'App.jsx'), 'utf-8');
    expect(src).not.toMatch(/healthApi\.get\(/);
    expect(src).toMatch(/metaApi\.get\(\)/);
    expect(src).toMatch(/kimlik_gerekli/);
  });
});
