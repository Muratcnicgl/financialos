/**
 * FE-024 (BUG #489): asılı istek sonsuza dek beklemez.
 *
 * Ölçüm (14 Eyl 2026): `request()` fetch'e signal vermiyordu; cevap gelmeyen bir istek panelleri
 * sonsuz "yükleniyor"da bırakıyordu. Kilitlenen: (1) varsayılan 30 sn'de ApiError(0, zaman aşımı),
 * (2) dış signal abort → "iptal edildi", (3) hızlı cevap etkilenmez ve zamanlayıcı temizlenir,
 * (4) koç sohbeti 180 sn ile çağırır (sağlayıcı zinciri), (5) fetch'e signal gerçekten geçer.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { request, accountsApi, coachApi, ISTEK_ZAMAN_ASIMI_MS, KOC_ZAMAN_ASIMI_MS } from './api.js';

function askidaFetch() {
  // signal'a saygılı, hiç cevaplamayan fetch
  return vi.fn((url, init) => new Promise((_, reject) => {
    init.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
  }));
}

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('FE-024 — istek zaman aşımı', () => {
  it('30 sn sonra ApiError(0) ve zaman aşımı metni', async () => {
    const f = askidaFetch();
    vi.stubGlobal('fetch', f);
    const soz = accountsApi.list();
    const beklenti = expect(soz).rejects.toMatchObject({ status: 0, message: expect.stringMatching(/zaman aşımı.*30 sn/) });
    await vi.advanceTimersByTimeAsync(ISTEK_ZAMAN_ASIMI_MS + 5);
    await beklenti;
    expect(f.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  });

  it('dış signal iptali "iptal edildi" der, zaman aşımı değil', async () => {
    vi.stubGlobal('fetch', askidaFetch());
    const ac = new AbortController();
    const soz = request('/api/accounts', { signal: ac.signal });
    const beklenti = expect(soz).rejects.toMatchObject({ status: 0, message: 'İstek iptal edildi.' });
    ac.abort();
    await beklenti;
    expect(vi.getTimerCount()).toBe(0);   // zaman aşımı zamanlayıcısı temizlendi
  });

  it('hızlı cevap etkilenmez, zamanlayıcı temizlenir', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => [{ id: 1 }],
    }));
    await expect(accountsApi.list()).resolves.toEqual([{ id: 1 }]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('koç sohbeti uzun zaman aşımıyla çağırır', async () => {
    const f = askidaFetch();
    vi.stubGlobal('fetch', f);
    const soz = coachApi.chat('merhaba');
    const beklenti = expect(soz).rejects.toMatchObject({ message: expect.stringMatching(/180 sn/) });
    await vi.advanceTimersByTimeAsync(ISTEK_ZAMAN_ASIMI_MS + 5);
    expect(f.mock.calls[0][1].signal.aborted).toBe(false);   // 30 sn'de hâlâ bekliyor
    await vi.advanceTimersByTimeAsync(KOC_ZAMAN_ASIMI_MS);
    await beklenti;
  });
});
