/**
 * BUG #253 — GİRİŞ YAPAMAYAN KULLANICININ "BENDE Mİ, SİZDE Mİ?" SORUSU CEVAPSIZDI.
 *
 * `/api/meta/durum` (ve BUG #247 ile `/api/ready`) uçları vardı ama bakabileceği bir yüzey
 * yoktu: elindeki tek bilgi "bir şeyler ters gitti"ydi — şifresini mi yanlış giriyor,
 * sunucu mu ölü, ayırt edemiyordu. Bilinmezlik, bilinen kesintiden çok destek yükü üretir.
 *
 * Kilitlenen sözleşme: kimlik istemez · 503'ü HATA değil SONUÇ olarak okur · ayrıntı
 * (tablo/hata/sürüm) sızdırmaz · ağ tamamen ölüyken de çökmez.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

import SistemDurumu from './components/SistemDurumu.jsx';

function fetchMock(yanit) {
  return vi.fn(async (url) => {
    if (typeof yanit === 'function') return yanit(url);
    return yanit;
  });
}

const OK = { status: 200, ok: true, json: async () => ({ hazir: true, db: 'ok' }) };
const NOT_READY = {
  status: 503, ok: false,
  json: async () => ({ detail: { hazir: false, db: 'erisilemiyor', sorunlar: [{ ad: 'db' }] } }),
};

afterEach(() => vi.unstubAllGlobals());

describe('BUG #253 — kimliksiz sistem durumu', () => {
  it('sağlıklı sistemde "çalışıyor" der', async () => {
    vi.stubGlobal('fetch', fetchMock(OK));
    render(<SistemDurumu onClose={() => {}} />);
    expect(await screen.findByText(/Sistem çalışıyor/)).toBeInTheDocument();
    expect(screen.getByText(/şifre\/davet kodunu kontrol et/)).toBeInTheDocument();
  });

  it('503 bir HATA değil SONUÇTUR — "sistemde sorun var" gösterir', async () => {
    vi.stubGlobal('fetch', fetchMock(NOT_READY));
    render(<SistemDurumu onClose={() => {}} />);
    expect(await screen.findByText(/Sistemde sorun var/)).toBeInTheDocument();
    expect(screen.getByText(/senin hatan değil/)).toBeInTheDocument();
  });

  it('sunucuya hiç ulaşılamıyorsa çökmez, durumu söyler', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    render(<SistemDurumu onClose={() => {}} />);
    expect(await screen.findByText(/Sunucuya ulaşılamıyor/)).toBeInTheDocument();
  });

  it('teşhis ayrıntısı (tablo/hata/sürüm) kullanıcıya SIZMAZ', async () => {
    vi.stubGlobal('fetch', fetchMock({
      status: 503, ok: false,
      json: async () => ({ detail: { sorunlar: [{ ad: 'sema', detay: 'migration koşulmamış (kod=f2a3b4c5d6e7)' }] } }),
    }));
    const { container } = render(<SistemDurumu onClose={() => {}} />);
    await screen.findByText(/Sistemde sorun var/);
    expect(container.textContent).not.toMatch(/f2a3b4c5d6e7|migration|sema/);
  });

  it('kimlik/token göndermez (giriş yapamayan kullanıcı içindir)', async () => {
    const sahte = fetchMock(OK);
    vi.stubGlobal('fetch', sahte);
    render(<SistemDurumu onClose={() => {}} />);
    await screen.findByText(/Sistem çalışıyor/);
    const [, init] = sahte.mock.calls[0];
    expect(JSON.stringify(init?.headers || {})).not.toMatch(/Authorization/i);
  });

  it('yeniden kontrol düğmesi ucu tekrar sorar', async () => {
    const sahte = fetchMock(OK);
    vi.stubGlobal('fetch', sahte);
    render(<SistemDurumu onClose={() => {}} />);
    await screen.findByText(/Sistem çalışıyor/);
    fireEvent.click(screen.getByRole('button', { name: /Yeniden kontrol et/ }));
    await waitFor(() => expect(sahte.mock.calls.length).toBeGreaterThanOrEqual(2));
  });
});
