/**
 * B2 / BUG #281 — hatadan geri bildirime TEK TIK zinciri.
 *
 * Kullanıcı hatayı gördüğü ANDA bildirebilmeli: "sonra widget'ı bul" demek pratikte
 * bildirmemektir, üstelik korelasyon kodu o an ekranda, sonra kaybolur. Kilitlenen
 * sözleşme: hata kartındaki "Bunu bildir" geri bildirim formunu AÇAR ve kodu forma
 * TAŞIR; gönderim o kodu sunucuya iletir.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('./api.js', async () => {
  const actual = await vi.importActual('./api.js');
  return { ...actual, feedbackApi: { create: vi.fn().mockResolvedValue({ id: 1 }) } };
});

import ErrorBoundary from './components/ErrorBoundary.jsx';
import { ApiError } from './api.js';
import * as api from './api.js';

function Patlayan({ hata }) {
  throw hata;
}

describe('hatadan bildirime zinciri', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('"Bunu bildir" formu açar ve kodu forma taşır', async () => {
    render(
      <ErrorBoundary>
        <Patlayan hata={new ApiError(500, 'hata', null, 'abc23xyz')} />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByTestId('hatadan-bildir'));
    expect(await screen.findByTestId('feedback-istek-id')).toHaveTextContent('abc23xyz');
  });

  it('gönderim kodu SUNUCUYA iletir', async () => {
    render(
      <ErrorBoundary>
        <Patlayan hata={new ApiError(500, 'hata', null, 'abc23xyz')} />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByTestId('hatadan-bildir'));
    const alan = await screen.findByPlaceholderText(/Ne düşünüyorsun/);
    fireEvent.change(alan, { target: { value: 'koç açılmadı' } });
    fireEvent.click(screen.getByRole('button', { name: /Gönder/ }));
    await waitFor(() => expect(api.feedbackApi.create).toHaveBeenCalled());
    const cagri = api.feedbackApi.create.mock.calls[0];
    expect(cagri[3]).toBe('abc23xyz');   // (kind, message, page, istekId)
  });

  it('kodsuz hatada da bildirim yapılabilir (form açılır, kod satırı çıkmaz)', async () => {
    render(
      <ErrorBoundary>
        <Patlayan hata={new TypeError('istemci çökmesi')} />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByTestId('hatadan-bildir'));
    expect(await screen.findByPlaceholderText(/Ne düşünüyorsun/)).toBeTruthy();
    expect(screen.queryByTestId('feedback-istek-id')).toBeNull();
  });

  it('"kafa karıştırdı" türü kullanıcıya sunulur', async () => {
    render(
      <ErrorBoundary>
        <Patlayan hata={new ApiError(500, 'hata', null, 'abc23xyz')} />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByTestId('hatadan-bildir'));
    expect(await screen.findByRole('button', { name: 'Kafa karıştırdı' })).toBeTruthy();
  });
});
