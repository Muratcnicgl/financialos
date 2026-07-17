/**
 * M64 — Frontend regresyon ağı (component + request davranışı).
 * tam-proje-durum-raporu B23d: 10.846 satır frontend / 33 test / 0 component testi.
 * M43 global X-Workspace-Id + WorkspaceSwitcher ekledi ama vitest 33→33 kalmıştı.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// --- basit presentational component'ler (smoke render) ---
import MetricCard from './components/MetricCard.jsx';
import EmptyState from './components/EmptyState.jsx';
import { Skeleton } from './components/Skeleton.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';

describe('M64 — presentational component smoke render', () => {
  it('MetricCard başlık + formatlanmış değeri gösterir', () => {
    render(<MetricCard title="Nakit" value={9747.95} />);
    expect(screen.getByText('Nakit')).toBeInTheDocument();
    expect(screen.getByText(/9\.747,95/)).toBeInTheDocument();  // TR format
  });

  it('MetricCard loading modunda çökmez', () => {
    const { container } = render(<MetricCard title="Kart" value="0" loading />);
    expect(container.firstChild).toBeTruthy();
  });

  it('EmptyState mesajı render eder', () => {
    render(<EmptyState title="Kayıt yok" message="Henüz veri girilmedi" />);
    expect(screen.getByText('Kayıt yok')).toBeInTheDocument();
  });

  it('Skeleton className ile render olur', () => {
    const { container } = render(<Skeleton className="h-4 w-32" />);
    expect(container.firstChild).toHaveClass('animate-pulse');
  });

  it('ErrorBoundary çocuğu normalde gösterir', () => {
    render(<ErrorBoundary><div>içerik</div></ErrorBoundary>);
    expect(screen.getByText('içerik')).toBeInTheDocument();
  });

  it('ErrorBoundary çöken çocukta yakalar (beyaz ekran yok)', () => {
    const Boom = () => { throw new Error('patla'); };
    // konsol hatasını bastır
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { container } = render(<ErrorBoundary><Boom /></ErrorBoundary>);
    expect(container.textContent.length).toBeGreaterThan(0);  // fallback UI var
    spy.mockRestore();
  });
});

// =============================================================
// request() header davranışı (Bearer + X-Workspace-Id) — M11/M43
// =============================================================
import { cockpitApi, setTokens, clearTokens, setActiveWorkspaceId } from './api.js';

describe('M64 — request() header davranışı', () => {
  let store, fetchMock;
  beforeEach(() => {
    store = {};
    vi.stubGlobal('localStorage', {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    });
    fetchMock = vi.fn().mockResolvedValue({
      status: 200, ok: true, headers: { get: () => 'application/json' },
      json: async () => ({ ok: 1 }),
    });
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('token varsa Authorization: Bearer eklenir', async () => {
    store.fos_access_token = 'ACC123';
    await cockpitApi.get();
    const init = fetchMock.mock.calls[0][1];
    expect(init.headers['Authorization']).toBe('Bearer ACC123');
  });

  it('token yoksa Authorization eklenmez', async () => {
    await cockpitApi.get();
    const init = fetchMock.mock.calls[0][1];
    expect(init.headers['Authorization']).toBeUndefined();
  });

  it('aktif workspace varsa X-Workspace-Id eklenir', async () => {
    store.financialos_active_workspace_id = '7';
    await cockpitApi.get();
    const init = fetchMock.mock.calls[0][1];
    expect(init.headers['X-Workspace-Id']).toBe('7');
  });

  it('aktif workspace yoksa X-Workspace-Id eklenmez', async () => {
    await cockpitApi.get();
    const init = fetchMock.mock.calls[0][1];
    expect(init.headers['X-Workspace-Id']).toBeUndefined();
  });
});

// =============================================================
// WorkspaceSwitcher (M43) — mock'lu api ile
// =============================================================
// Yalnız workspaceApi.list mock'lanır; getActiveWorkspaceId/setActiveWorkspaceId GERÇEK kalır
// (request() header testleri onlara bağlı — mock'larsak kırılır).
vi.mock('./api.js', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, workspaceApi: { list: vi.fn() } };
});

import { WorkspaceSwitcher } from './App.jsx';
import * as api from './api.js';

describe('M64 — WorkspaceSwitcher', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('tek workspace varsa seçici GÖSTERİLMEZ (gereksiz)', async () => {
    api.workspaceApi.list.mockResolvedValue([{ id: 1, name: 'Kişisel', is_personal: true, role: 'owner' }]);
    const { container } = render(<WorkspaceSwitcher />);
    // async list sonrası re-render; başta da select yok
    expect(container.querySelector('select')).toBeNull();
  });

  it('birden çok workspace varsa seçici GÖRÜNÜR + seçenekleri listeler', async () => {
    api.workspaceApi.list.mockResolvedValue([
      { id: 1, name: 'Kişisel', is_personal: true, role: 'owner' },
      { id: 2, name: 'Aile', is_personal: false, role: 'editor' },
    ]);
    render(<WorkspaceSwitcher />);
    const sel = await screen.findByTitle('Aktif workspace');
    expect(sel).toBeInTheDocument();
    expect(screen.getByText(/Aile/)).toBeInTheDocument();
    expect(screen.getByText(/Kişisel/)).toBeInTheDocument();
  });
});

// =============================================================
// authApi + request edge davranışları (fetch mock)
// =============================================================
import { authApi, ApiError } from './api.js';

describe('M64 — authApi + request edge', () => {
  let store, fetchMock;
  beforeEach(() => {
    store = {};
    vi.stubGlobal('localStorage', {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  const okJson = (data) => ({ status: 200, ok: true, headers: { get: () => 'application/json' }, json: async () => data });

  it('login POST /api/auth/login + token kaydeder', async () => {
    fetchMock = vi.fn().mockResolvedValue(okJson({ access_token: 'A', refresh_token: 'R' }));
    vi.stubGlobal('fetch', fetchMock);
    await authApi.login({ email: 'a@b.com', password: 'x' });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/login');
    expect(store.fos_access_token).toBe('A');
    expect(store.fos_refresh_token).toBe('R');
  });

  it('register POST /api/auth/register + KVKK body geçer', async () => {
    fetchMock = vi.fn().mockResolvedValue(okJson({ access_token: 'A2', refresh_token: 'R2' }));
    vi.stubGlobal('fetch', fetchMock);
    await authApi.register({ email: 'y@x.com', password: 'p', name: 'Y', kvkk_consent: true });
    const init = fetchMock.mock.calls[0][1];
    expect(JSON.parse(init.body).kvkk_consent).toBe(true);
  });

  it('passwordResetRequest doğru endpoint', async () => {
    fetchMock = vi.fn().mockResolvedValue({ status: 204, ok: true, headers: { get: () => '' } });
    vi.stubGlobal('fetch', fetchMock);
    const r = await authApi.passwordResetRequest('a@b.com');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/password-reset-request');
    expect(r).toBeNull();  // 204 → null
  });

  it('isLoggedIn token durumunu yansıtır', () => {
    expect(authApi.isLoggedIn()).toBe(false);
    store.fos_access_token = 'T';
    expect(authApi.isLoggedIn()).toBe(true);
  });

  it('oauthLogin provider URL\'ine yönlendirir', () => {
    const loc = { href: '' };
    vi.stubGlobal('window', { location: loc });
    authApi.oauthLogin('google');
    expect(loc.href).toBe('/api/auth/oauth/google/login');
  });

  it('204 → null döner', async () => {
    fetchMock = vi.fn().mockResolvedValue({ status: 204, ok: true, headers: { get: () => '' } });
    vi.stubGlobal('fetch', fetchMock);
    expect(await cockpitApi.get()).toBeNull();
  });

  it('network hatası → ApiError(0)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    await expect(cockpitApi.get()).rejects.toBeInstanceOf(ApiError);
    await expect(cockpitApi.get()).rejects.toMatchObject({ status: 0 });
  });

  it('4xx (auth dışı) → ApiError + detail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      status: 404, ok: false, headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'bulunamadı' }) }));
    await expect(cockpitApi.get()).rejects.toMatchObject({ status: 404, message: 'bulunamadı' });
  });
});

// =============================================================
// workspaceApi (M41/M42) — endpoint + X-Workspace-Id
// =============================================================
describe('M64 — workspaceApi endpoint davranışı', () => {
  let store, fetchMock;
  beforeEach(() => {
    store = {};
    vi.stubGlobal('localStorage', {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    });
    fetchMock = vi.fn().mockResolvedValue({ status: 200, ok: true, headers: { get: () => 'application/json' }, json: async () => ({}) });
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('invite X-Workspace-Id header ile POST', async () => {
    const { workspaceApi } = await vi.importActual('./api.js');
    await workspaceApi.invite(5, 'x@y.com', 'viewer');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/workspaces/5/invite');
    expect(fetchMock.mock.calls[0][1].headers['X-Workspace-Id']).toBe('5');
  });

  it('join token query-param ile GET', async () => {
    const { workspaceApi } = await vi.importActual('./api.js');
    await workspaceApi.join('TKN');
    expect(fetchMock.mock.calls[0][0]).toContain('/api/workspaces/join?token=TKN');
  });

  it('create POST /api/workspaces', async () => {
    const { workspaceApi } = await vi.importActual('./api.js');
    await workspaceApi.create('Aile');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/workspaces');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).name).toBe('Aile');
  });
});

// =============================================================
// getJoinTokenFromUrl (M42) + ek smoke'lar
// =============================================================
import { getJoinTokenFromUrl } from './api.js';

describe('M64 — getJoinTokenFromUrl + ek smoke', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('/workspaces/join?token=X → token', () => {
    vi.stubGlobal('window', { location: { pathname: '/workspaces/join', search: '?token=INV42' } });
    expect(getJoinTokenFromUrl()).toBe('INV42');
  });

  it('join path değil → null', () => {
    vi.stubGlobal('window', { location: { pathname: '/', search: '?token=X' } });
    expect(getJoinTokenFromUrl()).toBeNull();
  });

  it('MetricCard negatif variant render olur', () => {
    render(<MetricCard title="Kredi" value={86482.42} variant="negative" />);
    expect(screen.getByText('Kredi')).toBeInTheDocument();
  });

  it('MetricCard emanet rozeti çökmez', () => {
    const { container } = render(<MetricCard title="Emanet" value={7360.44} isEmanet />);
    expect(container.firstChild).toBeTruthy();
  });

  it('EmptyState yalnız title ile render olur', () => {
    render(<EmptyState title="Boş" />);
    expect(screen.getByText('Boş')).toBeInTheDocument();
  });
});
