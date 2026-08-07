/**
 * P4.4 — BUG #215/#216: KVKK hakları ARAYÜZDEN ulaşılamıyordu.
 *
 * Backend'de export/silme uçları vardı ama hiçbir panel onları çağırmıyordu; e-postayı
 * değiştiren uç ise hiç yoktu. Tek "Verimi indir" bağlantısı düz <a href> olduğu için
 * Authorization başlığı taşımıyordu → giriş açıkken 401 indiriyordu.
 * L8 dersi: belgelenen ≠ ulaşılabilir. Bu testler hakların fiilen tıklanabilir olduğunu
 * ve indirmenin YETKİLİ istekle yapıldığını kilitler.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { readFileSync } from 'node:fs';

vi.mock('./api.js', () => ({
  ApiError: class ApiError extends Error {},
  clearTokens: vi.fn(),
  userApi: { get: vi.fn().mockResolvedValue({ name: 'Beta', email: 'beta@ornek.com' }) },
  authApi: {
    me: vi.fn().mockResolvedValue({ name: 'Beta', email: 'beta@ornek.com' }),
    changeEmail: vi.fn().mockResolvedValue({ message: 'Doğrulama bağlantısı gönderildi.' }),
    changePassword: vi.fn().mockResolvedValue({}),
    exportData: vi.fn().mockResolvedValue({ user: { id: 1 }, transactions: [] }),
    deleteMe: vi.fn().mockResolvedValue(null),
  },
  // BUG #262: panel rehberi geri açma yerini de barındırır (gizleme geri alınabilir olmalı).
  onboardingApi: {
    rehber: vi.fn().mockResolvedValue({
      adimlar: [], tamamlanan: 1, toplam: 4, tamamlandi: false, gizli: true, gorunur: false,
    }),
    rehberGizle: vi.fn().mockResolvedValue({
      adimlar: [], tamamlanan: 1, toplam: 4, tamamlandi: false, gizli: false, gorunur: true,
    }),
  },
}));

import Hesap from './panels/Hesap.jsx';
import { authApi } from './api.js';

beforeEach(() => vi.clearAllMocks());

describe('Hesap paneli — KVKK hakları ulaşılabilir', () => {
  it('e-posta değiştirme formu backend ucunu çağırır', async () => {
    render(<Hesap />);
    fireEvent.change(screen.getByLabelText('Yeni e-posta'), { target: { value: 'yeni@ornek.com' } });
    fireEvent.change(screen.getByLabelText('Mevcut şifre (e-posta)'), { target: { value: 's1' } });
    fireEvent.click(screen.getByText('Doğrulama bağlantısı gönder'));
    await waitFor(() => expect(authApi.changeEmail).toHaveBeenCalledWith('yeni@ornek.com', 's1'));
  });

  it('doğrulama beklendiği kullanıcıya söylenir (adres hemen değişmez)', async () => {
    render(<Hesap />);
    fireEvent.change(screen.getByLabelText('Yeni e-posta'), { target: { value: 'y@o.com' } });
    fireEvent.change(screen.getByLabelText('Mevcut şifre (e-posta)'), { target: { value: 's' } });
    fireEvent.click(screen.getByText('Doğrulama bağlantısı gönder'));
    expect(await screen.findByRole('status')).toHaveTextContent(/Doğrulama bağlantısı/);
  });

  it('şifre değiştirme ucu çağrılır', async () => {
    render(<Hesap />);
    fireEvent.change(screen.getByLabelText('Mevcut şifre'), { target: { value: 'eski' } });
    fireEvent.change(screen.getByLabelText('Yeni şifre'), { target: { value: 'YeniSifre123' } });
    fireEvent.click(screen.getByText('Şifreyi değiştir'));
    await waitFor(() =>
      expect(authApi.changePassword).toHaveBeenCalledWith('eski', 'YeniSifre123'));
  });

  it('veri indirme YETKİLİ istekle yapılır (düz link değil)', async () => {
    global.URL.createObjectURL = vi.fn(() => 'blob:x');
    global.URL.revokeObjectURL = vi.fn();
    render(<Hesap />);
    fireEvent.click(screen.getByText('Verilerimi indir'));
    await waitFor(() => expect(authApi.exportData).toHaveBeenCalled());
  });

  it('hesap silme yazılı onay olmadan tetiklenemez', async () => {
    render(<Hesap />);
    const btn = screen.getByText('Hesabımı kalıcı olarak sil');
    fireEvent.click(btn);
    expect(authApi.deleteMe).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Silme onayı'), { target: { value: 'HESABIMI SIL' } });
    fireEvent.click(btn);
    await waitFor(() => expect(authApi.deleteMe).toHaveBeenCalled());
  });
});

describe('BUG #216 drift kilidi', () => {
  it('App.jsx yetkisiz <a href> export bağlantısı içermez', () => {
    const kaynak = readFileSync('src/App.jsx', 'utf-8');
    expect(kaynak).not.toMatch(/href="\/api\/user(s\/me)?\/export"/);
  });
});
