/**
 * COCKPIT SADE GÖRÜNÜM KAPISI — sadeleştirmenin RİSKİ gizlemediğini ölçer.
 *
 * Sade görünüm, Cockpit'teki analiz bölümlerini gizler. Bu kolayca kötü bir şeye
 * dönüşebilirdi: "az göster" uğruna kullanıcının PARA KAYBETTİREN sinyallerini de
 * yutmak. O yüzden gizlenebilir olanla olmayan burada AYRILIR ve kilitlenir.
 *
 * Sade görünümde de GÖRÜNMEK ZORUNDA olanlar:
 *   - kritik/uyarı seviyesindeki alerts (backend'in "bu tehlikeli" dediği şey)
 *   - onay bekleyen aksiyonlar (kullanıcının kararını bekleyen para hareketi)
 *   - vadesi gelip öneriye dönüşemeyen düzenli kayıtlar (BUG #273 sınıfı sessizlik)
 *   - "ilk adım" (deterministik en yüksek etkili hamle)
 *   - bugünkü harcama hedefi ve hesapların durumu
 *   - BAYAT FİYAT: ekrandaki yatırım sayılarını yanlış yapar; analiz değil veri kalitesi
 *
 * Gizlenebilir olanlar (yalnız detaylı görünümde): faiz sızıntısı, kart kullanım oranı,
 * alacak yaşlandırma, asgari ödeme tuzağı, akış özeti, stratejik göstergeler...
 * — ve gizlenen bölümlerin SAYISI ile ADLARI ekranda yazılı olmak zorunda.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { yazModu, BASIT, DETAYLI } from './lib/gorunumModu.js';

const COCKPIT = {
  statu: 'Nakit akışın dengede.',
  nakit_kasa: 12000, kart_borcu: 3000, kredi_borcu: 8000, yatirim_deger: 5000,
  emanet_kasa: 1000, beklenen_gelir: 20000, reel_butce: 15000,
  net_deger: 6000, net_deger_tam: 9000, alacaklar_toplami: 3000, borclar_toplami: 0,
  today_target: 660, daily_limit: 620, days_remaining: 22, carried_forward: 40,
  yarin_limit_harcamasiz: 690, guvenli_harcama: 4200, nakit_runway_gun: 41,
  butce_dokum: {
    nakit: 12000, beklenen_gelir: 20000, kart_borcu: 3000, bu_ayki_taksit: 1800,
    reel_butce: 15000, days_remaining: 22, daily_limit: 620, alacak_haric: 3000,
  },
  sonraki_eylem: { tip: 'firsat', eylem: 'Kart borcunu kapat', gerekce: 'Faiz en pahalı kalemin.' },
  saglik_skoru: { skor: 72, seviye: 'orta', bilesenler: [{ ad: 'Likidite', puan: 18 }] },
  alerts: [
    // Kodsuz uyarı: hiçbir zaman bastırılmaz (eski kayıtlar da güvende olmalı).
    { seviye: 'kritik', baslik: 'Kart limiti kritik', mesaj: 'Limitin %92 dolu.' },
    // Adanmış kartı OLAN uyarı: detaylı görünümde bastırılır, sade görünümde kalır.
    { seviye: 'uyari', kod: 'kart_kullanim_kritik',
      baslik: 'Kart kullanım oranı %95 üzeri', mesaj: 'Kart 92.0% dolu.' },
  ],
  gizli_uyari_sayisi: 0,
  accounts: [{ id: 1, ad: 'Nakit Kasa', account_type: 'cash', bakiye: 12000 }],
  investment_pnl: [{ toplam_maliyet: 4000, guncel_deger: 5000, brut_kar: 1000, getiri_yuzde: 25 }],
  abonelik_yuku: { adet: 3, aylik: 450, yillik: 5400 },
  borc_ozgurluk: { asla_bitmez: false, kalan_ay: 14, borcsuz_tarih: '2027-11-01', toplam_faiz: 2400 },
  faiz_sizintisi: { aylik_toplam: 320, yillik_toplam: 3840, gunluk: 10.5 },
  kart_kullanim: { band: 'kritik', oran: 92, toplam_borc: 3000, toplam_limit: 3260,
                   saglikli_borc_hedefi: 978, trend: null },
  alacak_yaslanma: { gecikmis_adet: 1, toplam_gecikmis: 1500, adet: 2,
                     en_riskli: [{ kim: 'Ali', tutar: 1500, gecikme_gun: 12 }] },
  asgari_tuzagi: { kartlar: [{ ad: 'Kart', ay: 62, toplam_faiz: 9000, payoff_tarih: '2031-01-01' }] },
  upcoming_reminders: [{ name: 'Kira', days_until: 2, type: 'expense', amount: 10000 }],
  upcoming_payments: [{ ad: 'Kredi taksiti', tarih: '2026-09-20', tip: 'kredi_taksit', tutar: 1800 }],
  upcoming_receivables: [{ kim: 'Ali', tarih: '2026-09-25', aciklama: 'borç', tutar: 1500 }],
  price_freshness: { stale_count: 0, items: [{ account_id: 9, name: 'Fon', age_text: '2 gün', is_stale: false }] },
};

const BEKLEYEN = [{
  id: 1, action_type: 'add_transaction',
  summary: 'Markete 250,00 TL harcama kaydedildi',
  payload: JSON.stringify({ account_id: 1, amount: 250, description: 'Market' }),
}];

const ATLANAN = [{ id: 'gelir-3', ad: 'Kira geliri', neden: 'hedef hesap silinmiş' }];

vi.mock('./api.js', async () => {
  const gercek = await vi.importActual('./api.js');
  return {
    ...gercek,
    cockpitApi: { get: vi.fn() },
    actionsApi: { pending: vi.fn(), approve: vi.fn(), reject: vi.fn(), edit: vi.fn() },
    incomesApi: { triggerDue: vi.fn() },
    expensesApi: { triggerDue: vi.fn() },
    cashflowApi: { getForecast: vi.fn() },
    fundPriceApi: { update: vi.fn() },
    // Sahte uç kümesi GERÇEK kullanımla aynı olmalı: `netWorthTrend` eksikti ve
    // Cockpit onu çağırınca 243 test geçtiği hâlde vitest yakalanmamış hatayla
    // kırmızı çıkıyordu. Eksik bir sahte uç, "test yeşil" ile "ürün sağlam" arasına
    // sessiz bir fark koyar.
    reportsApi: {
      monthlySummary: vi.fn().mockRejectedValue(new Error('kapalı')),
      monthlySeries: vi.fn().mockRejectedValue(new Error('kapalı')),   // BUG #428
      netWorthTrend: vi.fn().mockResolvedValue({ items: [] }),
    },
    onboardingApi: {
      rehber: vi.fn().mockResolvedValue({ adimlar: [], tamamlanan: 4, toplam: 4,
                                          tamamlandi: true, gizli: false, gorunur: false }),
      durum: vi.fn().mockResolvedValue({ demo_yuklu: false }),
    },
  };
});

// eslint-disable-next-line import/first
import Cockpit from './panels/Cockpit.jsx';
// eslint-disable-next-line import/first
import { cockpitApi, actionsApi, incomesApi, expensesApi, cashflowApi } from './api.js';

async function cizdir(mod, veri = COCKPIT) {
  yazModu(mod);
  cockpitApi.get.mockResolvedValue(veri);
  actionsApi.pending.mockResolvedValue(BEKLEYEN);
  incomesApi.triggerDue.mockResolvedValue({ triggered: [], atlanan: ATLANAN });
  expensesApi.triggerDue.mockResolvedValue({ triggered: [], atlanan: [] });
  cashflowApi.getForecast.mockResolvedValue({
    summary: { lowest_balance: 500, lowest_date: '2026-09-20', net_flow: 1200, crunch_count: 0 },
  });
  const r = render(<Cockpit setActiveTab={vi.fn()} />);
  // Yükleme iskeleti kalkana kadar bekle — "yok" iddiaları ancak veri gelince anlamlı.
  await screen.findByText('Bugünkü manzara');
  return r;
}

beforeEach(() => { localStorage.clear(); vi.clearAllMocks(); });
afterEach(() => localStorage.clear());

describe('sade görünüm — RİSK gizlenmez', () => {
  it('kritik uyarı sade görünümde de görünür', async () => {
    await cizdir(BASIT);
    expect(screen.getByText('Kart limiti kritik')).toBeInTheDocument();
  });

  it('onay bekleyen aksiyon sade görünümde de görünür', async () => {
    await cizdir(BASIT);
    expect(screen.getByText(/Onay bekleyen aksiyonlar/)).toBeInTheDocument();
  });

  it('öneriye dönüşemeyen düzenli kayıt sade görünümde de görünür (BUG #273)', async () => {
    await cizdir(BASIT);
    expect(screen.getByTestId('atlanan-duzenli-kayitlar')).toBeInTheDocument();
  });

  it('ilk adım, bugünkü hedef ve hesaplar sade görünümde durur', async () => {
    await cizdir(BASIT);
    expect(screen.getByText('İlk adım')).toBeInTheDocument();
    expect(screen.getByText('Bugün harcayabileceğin')).toBeInTheDocument();
    expect(screen.getByText(/^Hesaplar \(/)).toBeInTheDocument();
  });

  it('bayat fiyat sade görünümde de görünür — yanlış sayı, analiz değil veri riskidir', async () => {
    await cizdir(BASIT, {
      ...COCKPIT,
      price_freshness: { stale_count: 1,
        items: [{ account_id: 9, name: 'Fon', age_text: '31 gün', is_stale: true }] },
    });
    expect(screen.getByText('Fiyat tazeliği')).toBeInTheDocument();
  });

  it('fiyatlar TAZEYSE bölüm sade görünümde gizlenir (gösterecek bir risk yok)', async () => {
    await cizdir(BASIT);
    expect(screen.queryByText('Fiyat tazeliği')).not.toBeInTheDocument();
  });
});

describe('sade görünüm — ANALİZ gizlenir ama gizlendiği YAZILIR', () => {
  it('analiz bölümleri sade görünümde çizilmez', async () => {
    await cizdir(BASIT);
    expect(screen.queryByText(/Faize giden:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Kart kullanımı/)).not.toBeInTheDocument();
    expect(screen.queryByText(/gecikmiş alacak/)).not.toBeInTheDocument();
    expect(screen.queryByText('Önümüzdeki 30 gün')).not.toBeInTheDocument();
    expect(screen.queryByText('Stratejik manzara')).not.toBeInTheDocument();
    expect(screen.queryByText('Yatırım Kâr/Zarar')).not.toBeInTheDocument();
  });

  it('kaç bölümün gizlendiği SAYIYLA yazılır ve adları listelenir', async () => {
    await cizdir(BASIT);
    const satir = screen.getByText(/Sade görünümdesin — \d+ analiz bölümü gizli/);
    expect(satir).toBeInTheDocument();
    expect(screen.getByText(/Faiz sızıntısı/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Detaylı görünüme geç/ })).toBeInTheDocument();
  });

  it('gizli sayısı VERİYE göre üretilir — olmayan bölüm sayılmaz', async () => {
    const { unmount } = await cizdir(BASIT);
    const tam = Number(screen.getByText(/Sade görünümdesin — \d+ analiz bölümü gizli/)
      .textContent.match(/(\d+)/)[1]);
    unmount();

    // Faiz sızıntısı ve alacak yaşlandırma verisi olmayan bir kullanıcı: sayı düşmeli.
    await cizdir(BASIT, {
      ...COCKPIT,
      faiz_sizintisi: { aylik_toplam: 0, yillik_toplam: 0, gunluk: 0 },
      alacak_yaslanma: { gecikmis_adet: 0, toplam_gecikmis: 0, adet: 0, en_riskli: [] },
    });
    const az = Number(screen.getByText(/Sade görünümdesin — \d+ analiz bölümü gizli/)
      .textContent.match(/(\d+)/)[1]);
    expect(az).toBe(tam - 2);
  });
});

describe('detaylı görünüm — hiçbir bölüm eksilmez', () => {
  it('analiz bölümlerinin tamamı çizilir ve "gizli" satırı çıkmaz', async () => {
    await cizdir(DETAYLI);
    expect(screen.getByText(/Faize giden:/)).toBeInTheDocument();
    expect(screen.getByText('Stratejik manzara')).toBeInTheDocument();
    expect(screen.getByText('Operasyonel manzara')).toBeInTheDocument();
    expect(screen.getByText('Yatırım Kâr/Zarar')).toBeInTheDocument();
    // 30 günlük akış: artık üç sayı değil bir eğri. Bölümün VARLIĞI burada kilitlenir;
    // sade taraftaki "çizilmez" iddiası ancak burada "çizilir" denirse bir şey ölçer.
    expect(screen.getByText('Önümüzdeki 30 gün')).toBeInTheDocument();
    expect(screen.queryByText(/Sade görünümdesin/)).not.toBeInTheDocument();
  });

  it('bugünkü hedef her iki görünümde de en üstteki karttır', async () => {
    await cizdir(DETAYLI);
    expect(screen.getByText('Bugün harcayabileceğin')).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════
// AYNI GERÇEK İKİ KEZ YAZILMAZ — ama tek kaynak kapanınca susturulmaz
// ══════════════════════════════════════════════════════════════════════

describe('uyarı tekrarı', () => {
  it('detaylı görünümde adanmış kart çiziliyorsa aynı konunun uyarısı bastırılır', async () => {
    await cizdir(DETAYLI);
    // Adanmış kart duruyor
    expect(screen.getByText(/Kart kullanımı/)).toBeInTheDocument();
    // Aynı konunun uyarısı ikinci kez yazılmıyor
    expect(screen.queryByText('Kart kullanım oranı %95 üzeri')).not.toBeInTheDocument();
    // Kodsuz uyarı asla bastırılmaz
    expect(screen.getByText('Kart limiti kritik')).toBeInTheDocument();
  });

  it('bastırılan uyarı SESSİZCE kaybolmaz — kaç tanesi kartta gösteriliyor, yazılır', async () => {
    await cizdir(DETAYLI);
    expect(screen.getByText(/kartlarda ayrıntılı gösteriliyor/)).toBeInTheDocument();
  });

  it('sade görünümde kart gizli olduğu için uyarı BASTIRILMAZ (tek kaynak odur)', async () => {
    await cizdir(BASIT);
    expect(screen.queryByText(/Kart kullanımı/)).not.toBeInTheDocument();   // kart gizli
    expect(screen.getByText('Kart kullanım oranı %95 üzeri')).toBeInTheDocument();
  });
});

describe('UX-003 — kart doluluğu somut mesafeyle (BUG #425)', () => {
  it('detaylı görünümde kart kullanım kartı "limite X kaldı" der (3260 − 3000 = 260)', async () => {
    await cizdir(DETAYLI);
    const metin = screen.getByText(/limite .*260.* kaldı/);
    expect(metin).toBeInTheDocument();
  });
});

describe('UX-023 — bildirim yorgunluğu: kritik açık, gerisi katlanır (BUG #427)', () => {
  it('1 kritik + 4 uyarı → kritik + 2 görünür, "+2 uyarı daha" açar/kapatır', async () => {
    const veri = {
      ...COCKPIT,
      alerts: [
        { seviye: 'uyari', kod: 'u1', baslik: 'Uyarı bir', mesaj: 'm' },
        { seviye: 'kritik', kod: 'k1', baslik: 'Kritik nakit', mesaj: 'm' },
        { seviye: 'uyari', kod: 'u2', baslik: 'Uyarı iki', mesaj: 'm' },
        { seviye: 'uyari', kod: 'u3', baslik: 'Uyarı üç', mesaj: 'm' },
        { seviye: 'uyari', kod: 'u4', baslik: 'Uyarı dört', mesaj: 'm' },
      ],
      kart_kullanim: { ...COCKPIT.kart_kullanim, band: 'orta' },   // adanmış kart çizilmesin, bastırma karışmasın
    };
    await cizdir(DETAYLI, veri);
    expect(screen.getByText('Kritik nakit')).toBeInTheDocument();
    expect(screen.getByText('Uyarı bir')).toBeInTheDocument();
    expect(screen.getByText('Uyarı iki')).toBeInTheDocument();
    expect(screen.queryByText('Uyarı üç')).toBeNull();
    const dugme = screen.getByRole('button', { name: /\+2 uyarı daha/ });
    expect(dugme).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(dugme);
    expect(screen.getByText('Uyarı dört')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Daha az uyarı/ }));
    expect(screen.queryByText('Uyarı üç')).toBeNull();
  });
});

describe('DVIZ-005 — kart altında dönem farkı (BUG #429)', () => {
  it('donem_degisimi yokken hiçbir kartta fark satırı yok (sıfır uydurulmaz)', async () => {
    await cizdir(BASIT, { ...COCKPIT, donem_degisimi: null });
    expect(screen.queryAllByTestId('metric-degisim')).toHaveLength(0);
  });

  it('ay başı bazlı fark: nakit +, kart borcu − ve "ay başından beri"; etiket tarihi değilse tarih yazar', async () => {
    const dd = { baz_tarih: '2026-09-01', gun: 11, ay_basi: true,
                 nakit_kasa: 2000, kart_borcu: -500, kredi_borcu: 0, yatirim_deger: 100,
                 net_deger: 2600, net_deger_tam: 2600 };
    const { unmount } = await cizdir(BASIT, { ...COCKPIT, donem_degisimi: dd });
    const satirlar = screen.getAllByTestId('metric-degisim').map((e) => e.textContent);
    expect(satirlar.some((t) => t.includes('▲ +2.000,00') && t.includes('ay başından beri'))).toBe(true);
    expect(satirlar.some((t) => t.includes('▼ −500,00'))).toBe(true);
    unmount();
    await cizdir(BASIT, { ...COCKPIT, donem_degisimi: { ...dd, ay_basi: false, baz_tarih: '2026-09-05' } });
    expect(screen.getAllByTestId('metric-degisim').some((e) => /5 Eyl'den beri/.test(e.textContent))).toBe(true);
  });
});
