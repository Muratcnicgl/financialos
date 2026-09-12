/**
 * RULE-030 KAPISI (BUG #432) — NAKİT PROJEKSİYONU KAPSAMINI SÖYLER.
 *
 * Ölçülen (12 Eyl 2026): özet kartı "Mevcut Nakit" ve "Sıkışma Günü" gösteriyor ama
 * projeksiyonun YALNIZ nakit hesapları izlediğini, kart limitinin dahil olmadığını söyleyen
 * satır yoktu; kart %99 doluyken "eşik aşılmıyor" tek başına yanıltıcıydı.
 *
 * Kilitlenen: kapsam notu her zaman; kalan kart limiti varsa tutar + "borç, dahil değil";
 * sıkışma varken ve kart limiti > 0 iken köprü ipucu "borçlanarak" der; limit null ise tutar yok.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CashflowSummary from './components/CashflowSummary.jsx';

const OZET = { lowest_balance: 500, lowest_date: '2026-09-20', total_receivable: 0, total_payable: -1000,
               net_flow: -1000, crunch_count: 0, opening_balance: 1500, kapsam: 'nakit', kalan_kart_limiti: null };

describe('RULE-030 — tahmin kapsamı', () => {
  it('kart limiti bilinmiyorsa yalnız kapsam notu, tutar yok', () => {
    render(<CashflowSummary summary={OZET} />);
    const not = screen.getByTestId('kapsam-notu');
    expect(not).toHaveTextContent('Yalnız nakit hesaplar');
    expect(not.textContent).not.toMatch(/kart limiti/);
    expect(screen.getByText('Nakit eşik altına inmiyor')).toBeInTheDocument();
  });

  it('kalan kart limiti varsa tutar ve "borç, dahil değil"; sıkışmada köprü ipucu borç der', () => {
    render(<CashflowSummary summary={{ ...OZET, kalan_kart_limiti: 6000, crunch_count: 2 }} />);
    const not = screen.getByTestId('kapsam-notu');
    expect(not).toHaveTextContent('kalan kart limiti');
    expect(not).toHaveTextContent('6.000,00');
    expect(not).toHaveTextContent('borç, dahil değil');
    expect(screen.getByText(/kart köprü olabilir \(borçlanarak\)/)).toBeInTheDocument();
  });

  it('sıkışma var ama kart limiti 0 → köprü ipucu yok', () => {
    render(<CashflowSummary summary={{ ...OZET, kalan_kart_limiti: 0, crunch_count: 1 }} />);
    expect(screen.queryByText(/köprü/)).toBeNull();
    expect(screen.getByText('Nakit eşik altında')).toBeInTheDocument();
  });
});
