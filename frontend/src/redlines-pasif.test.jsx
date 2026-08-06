/**
 * BUG #232 — "Pasifleştir" bastıktan sonra kural HİÇBİR sekmede görünmüyor.
 *
 * Kök neden: GET /api/checkpoints backend'de `active_only=True` DEFAULT'lu
 * (app/routers/checkpoints.py). RedLines paneli listeyi parametresiz çekiyordu,
 * dolayısıyla pasif kayıt istemciye HİÇ ulaşmıyordu; panelin "Pasif" / "Hepsi"
 * filtreleri istemci-taraflı olduğu için boş kalıyor, başlıktaki "N pasif"
 * sayacı da hep 0 gösteriyordu. Aynı sebeple soft-delete edilen kural da
 * kullanıcı için "buharlaşıyordu" (tarihçe kalsın diye tasarlanan davranışın
 * tam tersi).
 *
 * Bu test fetch'i backend'in GERÇEK sözleşmesiyle taklit eder: `active_only`
 * verilmezse yalnız aktifler döner. Panel yanlış çağrı yaparsa test kırmızıdır.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

import RedLines from './panels/RedLines.jsx';

const AKTIF_KURAL = {
  id: 1,
  title: 'MC1 - Emanet dokunulmaz',
  description: 'Emanet hesabı satılamaz.',
  checkpoint_type: 'red_line',
  priority: 1,
  is_active: true,
  rule_type: null,
  rule_params: null,
  created_at: '2026-08-01T10:00:00+00:00',
};

const PASIF_KURAL = {
  id: 2,
  title: 'MC7 - Artık geçerli değil',
  description: 'Kullanıcı bu kuralı pasifleştirdi.',
  checkpoint_type: 'rule',
  priority: 2,
  is_active: false,
  rule_type: null,
  rule_params: null,
  created_at: '2026-08-02T10:00:00+00:00',
};

/** Backend sözleşmesini taklit eder: active_only default TRUE. */
function makeFetchMock(kayit) {
  return vi.fn(async (url, init = {}) => {
    const u = new URL(url, 'http://localhost');
    kayit.push(u.pathname + u.search);

    let govde;
    if (u.pathname === '/api/checkpoints') {
      const activeOnly = u.searchParams.get('active_only');
      const hepsi = activeOnly === 'false' || activeOnly === '0';
      govde = hepsi ? [AKTIF_KURAL, PASIF_KURAL] : [AKTIF_KURAL];
    } else if (/^\/api\/checkpoints\/\d+$/.test(u.pathname) && init.method === 'PUT') {
      govde = { ...AKTIF_KURAL, ...JSON.parse(init.body || '{}') };  // PUT → güncel kayıt
    } else if (u.pathname === '/api/accounts') {
      govde = [];
    } else {
      govde = { detail: 'Bulunamadı' };
      return {
        ok: false, status: 404, headers: { get: () => 'application/json' },
        json: async () => govde, text: async () => JSON.stringify(govde),
      };
    }
    return {
      ok: true, status: 200, headers: { get: () => 'application/json' },
      json: async () => govde, text: async () => JSON.stringify(govde),
    };
  });
}

describe('BUG #232 — pasif kurallar panelde görünür', () => {
  let kayit;

  beforeEach(() => {
    kayit = [];
    vi.stubGlobal('fetch', makeFetchMock(kayit));
  });

  afterEach(() => { vi.unstubAllGlobals(); });

  it('"Pasif" sekmesi pasifleştirilmiş kuralı listeler', async () => {
    render(<RedLines />);
    await waitFor(() => expect(screen.getByText(AKTIF_KURAL.title)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Pasif' }));
    expect(await screen.findByText(PASIF_KURAL.title)).toBeInTheDocument();
  });

  it('"Hepsi" sekmesi aktif + pasif kuralların ikisini de gösterir', async () => {
    render(<RedLines />);
    await waitFor(() => expect(screen.getByText(AKTIF_KURAL.title)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Hepsi' }));
    expect(await screen.findByText(PASIF_KURAL.title)).toBeInTheDocument();
    expect(screen.getByText(AKTIF_KURAL.title)).toBeInTheDocument();
  });

  it('başlıktaki sayaç pasifleri de sayar (hep "0 pasif" değil)', async () => {
    render(<RedLines />);
    expect(await screen.findByText(/1 aktif, 1 pasif/)).toBeInTheDocument();
  });

  it('pasifleştirme sonrası liste yenilenir ve kural kaybolmaz', async () => {
    render(<RedLines />);
    await waitFor(() => expect(screen.getByText(AKTIF_KURAL.title)).toBeInTheDocument());

    // Aktif kartın güç düğmesi → PUT is_active:false
    const kapat = screen.getByTitle('Pasifleştir');
    fireEvent.click(kapat);

    await waitFor(() => {
      const put = kayit.filter((y) => y.startsWith('/api/checkpoints/1'));
      expect(put.length).toBe(1);
    });

    // Yenileme çağrısı da pasifleri istemeli — aksi halde kullanıcı kuralı bir
    // daha hiçbir sekmede bulamaz (bug'ın ta kendisi).
    const listele = () => kayit.filter((y) => y === '/api/checkpoints' || y.startsWith('/api/checkpoints?'));
    await waitFor(() => expect(listele().length).toBeGreaterThanOrEqual(2));
    listele().forEach((y) => expect(y).toContain('active_only=false'));
  });
});
