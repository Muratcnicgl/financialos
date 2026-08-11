/**
 * B3 / BUG #280 — korelasyon kimliğinin KULLANICIYA bakan ucu.
 *
 * Zincirin son halkası ekrandır: davetli "şu kod çıktı" diyemiyorsa sunucu tarafındaki
 * kimlik hiçbir işe yaramaz. İki sözleşme kilitlenir:
 *   1. Sunucu isteğinden gelen hata (ApiError) kimliği taşır ve ekranda GÖRÜNÜR.
 *   2. Saf istemci çökmesinde kod GÖSTERİLMEZ — uydurulmuş kod hiçbir kayda karşılık
 *      gelmez ve iki tarafı da yanıltır (L33).
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import { ApiError } from './api.js';

function Patlayan({ hata }) {
  throw hata;
}

describe('ErrorBoundary korelasyon kimliği', () => {
  it('sunucu hatasının kimliğini kullanıcıya gösterir', () => {
    render(
      <ErrorBoundary>
        <Patlayan hata={new ApiError(500, 'Beklenmedik bir hata oluştu.', null, 'abc23xyz')} />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId('korelasyon-kimligi')).toHaveTextContent('abc23xyz');
  });

  it('saf istemci çökmesinde kod UYDURMAZ', () => {
    render(
      <ErrorBoundary>
        <Patlayan hata={new TypeError('undefined okunamadı')} />
      </ErrorBoundary>,
    );
    expect(screen.queryByTestId('korelasyon-kimligi')).toBeNull();
  });

  it('kimlik yokken ApiError de kod göstermez (boş kutu çıkmasın)', () => {
    render(
      <ErrorBoundary>
        <Patlayan hata={new ApiError(500, 'hata', null, null)} />
      </ErrorBoundary>,
    );
    expect(screen.queryByTestId('korelasyon-kimligi')).toBeNull();
  });

  it('hata kartı her durumda çıkar (beyaz ekran ASLA)', () => {
    render(
      <ErrorBoundary>
        <Patlayan hata={new TypeError('x')} />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/Bu panel yüklenemedi/)).toBeTruthy();
  });
});
