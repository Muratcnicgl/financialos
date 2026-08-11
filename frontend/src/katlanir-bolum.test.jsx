/**
 * KATLANIR BÖLÜM KAPISI — "sadeleştirme, gizleme değildir" sözleşmesi.
 *
 * Bir bölümü katlamak, kullanıcının o bilgiye ERİŞMESİNİ kolaylaştırmak içindir; onu
 * bilgiden mahrum etmek için değil. Katlama sessizce bir gizlemeye dönüşürse panel
 * "sadeleşmiş" görünür ama kullanıcı artık kararını veremez — ve bu, ekranı kalabalık
 * bırakmaktan daha kötüdür çünkü kayıp görünmez.
 *
 * Kilitlenen değişmezler:
 *   1. Katlıyken ÖZET görünür (kaç kalem, ne kadar).
 *   2. Dikkat gerektiren durum (`vurgu`) katlıyken de görünür.
 *   3. Açma/kapama hatırlanır — her açılışta aynı bölümü açmak zorunda kalmak,
 *      katlamayı bir engele çevirir.
 *   4. Başlık gerçek bir düğmedir (klavye + ekran okuyucu) ve aria-expanded taşır.
 */
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Bell } from 'lucide-react';

import KatlanirBolum from './components/KatlanirBolum.jsx';

afterEach(() => localStorage.clear());

describe('KatlanirBolum', () => {
  it('katlıyken özet görünür — bilgi eksilmez, yalnız detay saklanır', () => {
    render(
      <KatlanirBolum ikon={Bell} baslik="Yaklaşan ödemeler" ozet="4 kalem · 12.400 TL">
        <p>kira 10.000</p>
      </KatlanirBolum>
    );
    expect(screen.getByText('Yaklaşan ödemeler')).toBeInTheDocument();
    expect(screen.getByText('4 kalem · 12.400 TL')).toBeInTheDocument();
    expect(screen.queryByText('kira 10.000')).not.toBeInTheDocument();
  });

  it('açılınca detay gelir, özet kaybolmaz', () => {
    render(
      <KatlanirBolum baslik="Yatırım" ozet="+3.200 TL · %8">
        <p>detay satırı</p>
      </KatlanirBolum>
    );
    fireEvent.click(screen.getByRole('button', { name: /yatırım/i }));
    expect(screen.getByText('detay satırı')).toBeInTheDocument();
    expect(screen.getByText('+3.200 TL · %8')).toBeInTheDocument();
  });

  it('dikkat gerektiren durum katlıyken de görünür', () => {
    render(
      <KatlanirBolum baslik="Fiyat tazeliği" ozet="3 hesap" vurgu="2 eski">
        <p>liste</p>
      </KatlanirBolum>
    );
    expect(screen.getByText('2 eski')).toBeInTheDocument();
    expect(screen.queryByText('liste')).not.toBeInTheDocument();
  });

  it('varsayilanAcik ile açık başlar (bayat fiyat gibi durumlar için)', () => {
    render(
      <KatlanirBolum baslik="Fiyat tazeliği" varsayilanAcik>
        <p>liste</p>
      </KatlanirBolum>
    );
    expect(screen.getByText('liste')).toBeInTheDocument();
  });

  it('kullanıcının açtığı hâl hatırlanır', () => {
    const { unmount } = render(
      <KatlanirBolum baslik="Tahsilatlar" anahtar="test_tahsilat">
        <p>detay</p>
      </KatlanirBolum>
    );
    fireEvent.click(screen.getByRole('button', { name: /tahsilatlar/i }));
    expect(screen.getByText('detay')).toBeInTheDocument();
    unmount();

    render(
      <KatlanirBolum baslik="Tahsilatlar" anahtar="test_tahsilat">
        <p>detay</p>
      </KatlanirBolum>
    );
    expect(screen.getByText('detay')).toBeInTheDocument();
  });

  it('kapatılan hâl de hatırlanır — varsayılan açık olsa bile', () => {
    const { unmount } = render(
      <KatlanirBolum baslik="Bölüm" anahtar="test_kapali" varsayilanAcik>
        <p>detay</p>
      </KatlanirBolum>
    );
    fireEvent.click(screen.getByRole('button', { name: /bölüm/i }));
    unmount();

    render(
      <KatlanirBolum baslik="Bölüm" anahtar="test_kapali" varsayilanAcik>
        <p>detay</p>
      </KatlanirBolum>
    );
    expect(screen.queryByText('detay')).not.toBeInTheDocument();
  });

  it('anahtar verilmezse tercih sızmaz (bölümler birbirini etkilemez)', () => {
    const { unmount } = render(
      <KatlanirBolum baslik="A"><p>a detay</p></KatlanirBolum>
    );
    fireEvent.click(screen.getByRole('button', { name: 'A' }));
    unmount();

    render(<KatlanirBolum baslik="A"><p>a detay</p></KatlanirBolum>);
    expect(screen.queryByText('a detay')).not.toBeInTheDocument();
  });

  it('başlık erişilebilir bir düğme ve aria-expanded taşır', () => {
    render(<KatlanirBolum baslik="Bölüm"><p>detay</p></KatlanirBolum>);
    const dugme = screen.getByRole('button', { name: /bölüm/i });
    expect(dugme).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(dugme);
    expect(dugme).toHaveAttribute('aria-expanded', 'true');
  });
});
