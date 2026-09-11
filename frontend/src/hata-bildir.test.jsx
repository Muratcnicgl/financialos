/**
 * OBS-013 KAPISI (BUG #406) — İSTEMCİ HATALARI SUNUCU DEFTERİNE.
 *
 * Ölçülen: ErrorBoundary konsola yazıyordu, o kadar; `window.onerror`/`unhandledrejection`
 * bağlı değildi; sunucu `error_logs` istemciyi hiç görmüyordu.
 * Kilitlenen: raporlayıcı aynı hatayı bir kez ve toplam en çok TAVAN gönderir, hiçbir zaman
 * fırlatmaz; global yakalayıcılar main.jsx'te bağlı; ErrorBoundary rapor eder.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { hataBildir, raporlanirMi, sifirla, globalYakalayicilariBagla, TAVAN } from './lib/hataBildir.js';

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return { ...gercek, istemciHataApi: { bildir: vi.fn().mockResolvedValue({ kayit_id: 1 }) } };
});
import ErrorBoundary from './components/ErrorBoundary.jsx';
import { istemciHataApi } from './api.js';

describe('hataBildir', () => {
  beforeEach(() => { sifirla(); istemciHataApi.bildir.mockClear(); });

  it('aynı parmak izi bir kez, toplam en çok TAVAN', () => {
    const gonder = vi.fn().mockResolvedValue(null);
    expect(hataBildir({ tip: 'TypeError', mesaj: 'x', yigin: 'a\nb', yol: '/' }, gonder)).toBe(true);
    expect(hataBildir({ tip: 'TypeError', mesaj: 'FARKLI mesaj', yigin: 'a\nb', yol: '/' }, gonder)).toBe(false);
    for (let i = 0; i < TAVAN + 5; i += 1) hataBildir({ tip: 'E', mesaj: 'm', yigin: `f${i}`, yol: '/' }, gonder);
    expect(gonder).toHaveBeenCalledTimes(TAVAN);
  });

  it('gönderici fırlatsa da reddetse de raporlayıcı fırlatmaz', () => {
    expect(() => hataBildir({ tip: 'A', yigin: '1' }, () => { throw new Error('ağ'); })).not.toThrow();
    expect(() => hataBildir({ tip: 'B', yigin: '2' }, () => Promise.reject(new Error('ağ')))).not.toThrow();
  });

  it('global yakalayıcılar error ve unhandledrejection olaylarını raporlar', () => {
    const gonder = vi.fn().mockResolvedValue(null);
    globalYakalayicilariBagla(gonder, () => '#test');
    window.dispatchEvent(new ErrorEvent('error', { message: 'patladı', error: new TypeError('patladı') }));
    const ev = new Event('unhandledrejection'); ev.reason = new RangeError('red');
    window.dispatchEvent(ev);
    expect(gonder).toHaveBeenCalledTimes(2);
    expect(gonder.mock.calls[0][0]).toMatchObject({ tip: 'TypeError', mesaj: 'patladı', yol: '#test' });
    expect(gonder.mock.calls[1][0]).toMatchObject({ tip: 'RangeError', mesaj: 'red' });
  });

  it('ErrorBoundary çöken paneli raporlar', () => {
    const Patlar = () => { throw new Error('render bombası'); };
    const sus = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<ErrorBoundary resetKey="cockpit"><Patlar /></ErrorBoundary>);
    sus.mockRestore();
    expect(istemciHataApi.bildir).toHaveBeenCalledTimes(1);
    expect(istemciHataApi.bildir.mock.calls[0][0]).toMatchObject({ mesaj: 'render bombası', yol: 'panel:cockpit' });
  });

  it('main.jsx global yakalayıcıları bağlar (kaynak bağı)', () => {
    const src = readFileSync(join(__dirname, 'main.jsx'), 'utf-8');
    expect(src).toMatch(/globalYakalayicilariBagla\(istemciHataApi\.bildir\)/);
  });
});
