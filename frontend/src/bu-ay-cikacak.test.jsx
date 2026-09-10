/**
 * BU AY ÇIKACAK — ikinci sayının kapısı.
 *
 * Ölçülen defekt (kullanıcı bildirimi, 10 Eyl 2026): ekranda tek bir sayı vardı
 * ("Bugün harcayabileceğin −49,97") ve o sayı MC4 gereği kart borcunun TAMAMINI
 * düşüyordu — bir STOK ile bir AKIŞ aynı kefede. Kullanıcı "saçma" dedi; haksız
 * değildi: o kartın 10.020,75'inin yalnız 6.576,90'ı bu ay çıkıyor.
 *
 * Kilitlenen: ikinci sayı GÖRÜNÜR, kendi aritmetiğini YAPMAZ (nakit_takvimi'nden okur)
 * ve varsayım kullandığında bunu SÖYLER.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import BuAyCikacak from './components/BuAyCikacak.jsx';

const TAKVIM = {
  baslangic_nakit: 15828.48,
  toplam_giris: 0,
  toplam_cikis: 13434.02,
  ay_sonu_bakiye: 2394.46,
  en_dusuk_bakiye: 2394.46,
  en_dusuk_tarih: '2026-09-15',
  acik_var: false,
  hesabi_belirsiz_toplam: 0,
  kalemler: [
    { tarih: '2026-09-11', ad: 'Kredi A', tutar: 4109.90, yon: 'cikis', tip: 'kredi_taksit' },
    { tarih: '2026-09-12', ad: 'Kart', tutar: 6576.90, yon: 'cikis', tip: 'kart_odeme',
      ekstre_biliniyor: true },
    { tarih: '2026-09-15', ad: 'Kredi B', tutar: 2747.22, yon: 'cikis', tip: 'kredi_taksit' },
  ],
};

describe('BuAyCikacak', () => {
  it('bu ayki GERCEK cikisi ve kalani gosterir', () => {
    render(<BuAyCikacak takvim={TAKVIM} gunKaldi={21} />);
    expect(screen.getByText(/13\.434,02/)).toBeInTheDocument();
    expect(screen.getByText(/2\.394,46/)).toBeInTheDocument();
  });

  it('gunluk tutari kalan / gun kaldi olarak gosterir', () => {
    render(<BuAyCikacak takvim={TAKVIM} gunKaldi={21} />);
    expect(screen.getByText(/114,02/)).toBeInTheDocument();
  });

  it('kart tutari guncel borctan geldiyse bunu SOYLER', () => {
    const t = { ...TAKVIM, kalemler: TAKVIM.kalemler.map(
      (k) => (k.tip === 'kart_odeme' ? { ...k, ekstre_biliniyor: false } : k)) };
    render(<BuAyCikacak takvim={t} gunKaldi={21} />);
    expect(screen.getByText(/güncel borçtan alındı/i)).toBeInTheDocument();
  });

  it('ekstre biliniyorsa varsayim notu YOKTUR', () => {
    render(<BuAyCikacak takvim={TAKVIM} gunKaldi={21} />);
    expect(screen.queryByText(/güncel borçtan alındı/i)).toBeNull();
  });

  it('ay sonu artida ama ay ORTASINDA dibe vuruyorsa sikismayi soyler', () => {
    render(<BuAyCikacak takvim={{ ...TAKVIM, acik_var: true, en_dusuk_bakiye: -820.5 }}
                        gunKaldi={21} />);
    expect(screen.getByText(/sıkışma orada/i)).toBeInTheDocument();
  });

  it('hesabi belirsiz gider varsa toplama girmedigini soyler', () => {
    render(<BuAyCikacak takvim={{ ...TAKVIM, hesabi_belirsiz_toplam: 8800 }} gunKaldi={21} />);
    expect(screen.getByText(/hesabı belirtilmemiş/i)).toBeInTheDocument();
  });

  it('takvim yoksa hicbir sey cizmez (uydurma sayi yok)', () => {
    const { container } = render(<BuAyCikacak takvim={null} gunKaldi={21} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('takvimde kalem yoksa satir da yoktur', () => {
    const { container } = render(
      <BuAyCikacak takvim={{ ...TAKVIM, toplam_cikis: 0, toplam_giris: 0 }} gunKaldi={21} />);
    expect(container).toBeEmptyDOMElement();
  });
});
