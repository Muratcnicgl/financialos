/**
 * FE-027 (BUG #490): hedef kuralı kriteri okunabilir; kural eklenebilir.
 *
 * Ölçüm (14 Eyl 2026): kural satırı `JSON.stringify(criteria)` gösteriyordu ("{"tx_type":"income",
 * "amount_min":5000} → %10"); sekmede yalnız SİLME vardı — kural hiçbir arayüzden yaratılamıyordu
 * (yalnız API). Kilitlenen: (1) formatter altı kriter anahtarını Türkçe yazar, bilinmeyeni ham
 * bırakır; (2) form kriter nesnesini boş alan girmeden kurar, kritersiz kaydı reddeder;
 * (3) RulesTab formu POST gövdesini backend şemasıyla (`GoalRuleCreate`) uyumlu gönderir.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { kriterMetni, ayirmaMetni, kriterOlustur } from './lib/kuralKriteri.js';
import { parseTRNumber } from './api.js';

describe('FE-027 — kriter metni', () => {
  it('altı anahtarı Türkçe yazar, bilinmeyeni ham bırakır, boşu "her işlem" der', () => {
    const m = kriterMetni({ tx_type: 'income', amount_min: 5000, amount_max: 9000, account_id: 3, account_type: ['cash', 'loan'], description_contains: 'maaş', x: 1 },
      [{ id: 3, name: 'Nakit Kasa' }]);
    expect(m).toContain('gelir işlemleri');
    expect(m).toMatch(/tutar ≥ .*5\.000/);
    expect(m).toMatch(/tutar ≤ .*9\.000/);
    expect(m).toContain('hesap: Nakit Kasa');
    expect(m).toContain('hesap tipi: nakit/kredi');
    expect(m).toContain('açıklamada "maaş"');
    expect(m).toContain('x=1');
    expect(kriterMetni({})).toBe('her işlem');
    expect(kriterMetni(null)).toBe('her işlem');
    expect(ayirmaMetni({ allocation_type: 'percent', allocation_value: 10 })).toBe('%10 ayrılır');
    expect(ayirmaMetni({ allocation_type: 'full' })).toBe('tamamı ayrılır');
  });

  it('formdan kriter: boş alan girmez, kritersiz null', () => {
    expect(kriterOlustur({ txType: 'income', amountMin: '5.000', descriptionContains: '  ' }, parseTRNumber))
      .toEqual({ tx_type: 'income', amount_min: 5000 });
    expect(kriterOlustur({ txType: '', amountMin: '', descriptionContains: '' }, parseTRNumber)).toBeNull();
    expect(kriterOlustur({ txType: '', amountMin: 'abc', descriptionContains: 'kira' }, parseTRNumber)).toEqual({ description_contains: 'kira' });
  });
});

describe('FE-027 — kural formu', () => {
  it('kural ekle → POST gövdesi şemayla uyumlu; kritersiz kayıt reddedilir', async () => {
    vi.doMock('./api.js', async () => {
      const gercek = await vi.importActual('./api.js');
      return { ...gercek, goalsApi: { ...gercek.goalsApi, rules: { list: vi.fn(), create: vi.fn().mockResolvedValue({ id: 5 }), delete: vi.fn() } } };
    });
    const { RulesTab } = await import('./panels/Goals.jsx');
    const { goalsApi } = await import('./api.js');
    const { ToastProvider } = await import('./components/Toast.jsx');
    const onRefresh = vi.fn();
    render(<ToastProvider><RulesTab rules={[]} goalId={7} onRefresh={onRefresh} /></ToastProvider>);
    fireEvent.click(screen.getByRole('button', { name: /Kural ekle/ }));
    fireEvent.change(screen.getByLabelText('Kural adı'), { target: { value: 'Maaşın onda biri' } });
    fireEvent.change(screen.getByLabelText('İşlem türü'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Kaydet' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/En az bir kriter/);
    expect(goalsApi.rules.create).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('İşlem türü'), { target: { value: 'income' } });
    fireEvent.change(screen.getByLabelText(/Tutar en az/), { target: { value: '5.000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Kaydet' }));
    await waitFor(() => expect(goalsApi.rules.create).toHaveBeenCalledTimes(1));
    expect(goalsApi.rules.create).toHaveBeenCalledWith(7, {
      name: 'Maaşın onda biri', criteria: { tx_type: 'income', amount_min: 5000 },
      allocation_type: 'percent', allocation_value: 10, is_active: true,
    });
    expect(onRefresh).toHaveBeenCalled();
    vi.doUnmock('./api.js');
  });
});
