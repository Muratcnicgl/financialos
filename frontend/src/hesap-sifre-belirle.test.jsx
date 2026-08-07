/**
 * BUG #233 — Google ile açılmış hesapta Hesap paneli ÇIKMAZ SOKAK çiziyordu.
 *
 * Kullanıcı bildirimi: "Google ile giriş yaptığım için e-posta doğru görünüyor ama şifre
 * kısmı 'eski şifreni gir, yeni şifre belirle' mantığında — benim eski şifrem yok."
 *
 * Panel her hesabın şifresi olduğunu varsayıyordu: "Mevcut şifren" alanı `required` idi,
 * yani kullanıcının gönderemeyeceği bir form. (Gönderebilse bile backend haklı olarak
 * 400 dönerdi.) Artık `/auth/me` yanıtındaki `has_password` ile dallanır.
 *
 * Ayrıca EKSİK alan durumunda KLASİK forma düşülmeli: yanlışlıkla "Şifre belirle"
 * göstermek, şifresi olan kullanıcıyı backend'in reddettiği bir uca sürükler.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const OAUTH_PROFIL = {
  name: 'Beta', email: 'beta@ornek.com', oauth_provider: 'google', has_password: false,
};
const SIFRELI_PROFIL = {
  name: 'Beta', email: 'beta@ornek.com', oauth_provider: null, has_password: true,
};

vi.mock('./api.js', () => ({
  ApiError: class ApiError extends Error {},
  clearTokens: vi.fn(),
  userApi: { get: vi.fn().mockResolvedValue({}) },
  authApi: {
    me: vi.fn(),
    changeEmail: vi.fn().mockResolvedValue({ message: 'ok' }),
    changePassword: vi.fn().mockResolvedValue({}),
    setPassword: vi.fn().mockResolvedValue({ access_token: 'a', refresh_token: 'r' }),
    exportData: vi.fn().mockResolvedValue({}),
    deleteMe: vi.fn().mockResolvedValue(null),
  },
  // BUG #262: panel ilk kurulum rehberini de okur (gizleme geri alınabilir olmalı).
  onboardingApi: {
    rehber: vi.fn().mockResolvedValue({
      adimlar: [], tamamlanan: 0, toplam: 4, tamamlandi: false, gizli: false, gorunur: true,
    }),
    rehberGizle: vi.fn().mockResolvedValue({
      adimlar: [], tamamlanan: 0, toplam: 4, tamamlandi: false, gizli: true, gorunur: false,
    }),
  },
}));

import Hesap from './panels/Hesap.jsx';
import { authApi } from './api.js';

beforeEach(() => vi.clearAllMocks());

describe('BUG #233 — şifresiz (OAuth) hesap şifre belirleyebilir', () => {
  it('şifresi olmayan hesapta "Mevcut şifren" İSTENMEZ', async () => {
    authApi.me.mockResolvedValue(OAUTH_PROFIL);
    render(<Hesap />);

    expect(await screen.findByRole('heading', { name: 'Şifre belirle' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Mevcut şifre')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Şifreni değiştir' })).not.toBeInTheDocument();
  });

  it('şifre belirleme ucu çağrılır ve kullanıcıya sonuç söylenir', async () => {
    authApi.me.mockResolvedValue(OAUTH_PROFIL);
    render(<Hesap />);
    await screen.findByRole('heading', { name: 'Şifre belirle' });

    fireEvent.change(screen.getByLabelText('Yeni şifre'), { target: { value: 'Belirlenen-123!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Şifre belirle' }));

    await waitFor(() => expect(authApi.setPassword).toHaveBeenCalledWith('Belirlenen-123!'));
    expect(await screen.findByRole('status')).toHaveTextContent(/Şifren belirlendi/);
  });

  it('belirledikten sonra panel klasik "şifre değiştir" formuna geçer', async () => {
    authApi.me.mockResolvedValue(OAUTH_PROFIL);
    render(<Hesap />);
    await screen.findByRole('heading', { name: 'Şifre belirle' });

    fireEvent.change(screen.getByLabelText('Yeni şifre'), { target: { value: 'Belirlenen-123!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Şifre belirle' }));

    expect(await screen.findByRole('heading', { name: 'Şifreni değiştir' })).toBeInTheDocument();
  });

  it('şifresi olmayan hesapta e-posta formu da şifre istemez (aynı kökün 2. kolu)', async () => {
    authApi.me.mockResolvedValue(OAUTH_PROFIL);
    render(<Hesap />);
    await screen.findByRole('heading', { name: 'Şifre belirle' });

    expect(screen.queryByLabelText('Mevcut şifre (e-posta)')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Yeni e-posta'), { target: { value: 'y@o.com' } });
    fireEvent.click(screen.getByText('Doğrulama bağlantısı gönder'));
    await waitFor(() => expect(authApi.changeEmail).toHaveBeenCalled());
  });

  it('şifresi OLAN hesapta klasik form korunur (regresyon)', async () => {
    authApi.me.mockResolvedValue(SIFRELI_PROFIL);
    render(<Hesap />);

    expect(await screen.findByRole('heading', { name: 'Şifreni değiştir' })).toBeInTheDocument();
    expect(screen.getByLabelText('Mevcut şifre')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Şifre belirle' })).not.toBeInTheDocument();
  });

  it('bayrak EKSİKSE klasik forma düşülür (yanlış yönlendirme yerine bilinen davranış)', async () => {
    authApi.me.mockResolvedValue({ name: 'Beta', email: 'beta@ornek.com' });
    render(<Hesap />);

    expect(await screen.findByRole('heading', { name: 'Şifreni değiştir' })).toBeInTheDocument();
  });
});
