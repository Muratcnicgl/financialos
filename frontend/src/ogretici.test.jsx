/**
 * ÖĞRETİCİ SİSTEM KAPISI — panel ipucu + kurulum sihirbazı + yardım köşesi.
 *
 * Bu kapının asıl işi üç ayrışmayı önlemek. Öğretici içeriği, koruduğu şeyden BAĞIMSIZ
 * yaşarsa sessizce yalan söylemeye başlar — ve yanlış öğreten bir yardım metni, hiç
 * olmayandan zararlıdır:
 *   1. Panel eklenir, rehberi yazılmaz → o ekranda yardım YOKTUR (kimse fark etmez).
 *   2. Sihirbazın "yaptın mı?" ölçütü backend'in bilmediği bir anahtara bakar → adım
 *      sonsuza kadar "yapılmadı" görünür.
 *   3. İçerik boşalır (ozet/örnek silinir) → şerit çizilir ama hiçbir şey öğretmez.
 *
 * Bu yüzden testler yalnız render etmiyor; içeriği KAYNAKLA karşılaştırıyor
 * (`App.jsx`'teki TABS listesi ve `app/routers/onboarding.py`'deki adım anahtarları).
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import Ipucu from './components/Ipucu.jsx';
import OgreticiSihirbaz from './components/OgreticiSihirbaz.jsx';
import YardimKosesi from './components/YardimKosesi.jsx';
import { PANEL_REHBERI, SIHIRBAZ_ADIMLARI, panelRehberi } from './lib/ogretici.js';

const BURASI = dirname(fileURLToPath(import.meta.url));

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function stubFetch(rehber) {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200,
    headers: { get: () => 'application/json' },
    json: async () => rehber,
  })));
}

const REHBER = {
  adimlar: [
    { anahtar: 'hesap', baslik: 'a', aciklama: '', sekme: 'accounts', tamam: true },
    { anahtar: 'islem', baslik: 'b', aciklama: '', sekme: 'transactions', tamam: false },
    { anahtar: 'kural', baslik: 'c', aciklama: '', sekme: 'redlines', tamam: false },
    { anahtar: 'koc', baslik: 'd', aciklama: '', sekme: 'coach', tamam: false },
  ],
  tamamlanan: 1, toplam: 4, tamamlandi: false, gizli: false, gorunur: true,
};

// ══════════════════════════════════════════════════════════════════════
// 1 — KAPSAM: her panelin rehberi VAR (yeni sekme eklenip unutulursa kırmızı)
// ══════════════════════════════════════════════════════════════════════

describe('kapsam', () => {
  it('App.jsx TABS listesindeki her sekmenin rehberi var', () => {
    const app = readFileSync(resolve(BURASI, 'App.jsx'), 'utf-8');
    const tabsBlogu = app.match(/const TABS = \[([\s\S]*?)\n\];/);
    expect(tabsBlogu, 'App.jsx içinde TABS listesi bulunamadı').toBeTruthy();

    const idler = [...tabsBlogu[1].matchAll(/id:\s*'([^']+)'/g)].map((m) => m[1]);
    expect(idler.length).toBeGreaterThan(5);   // liste gerçekten okundu mu

    const eksik = idler.filter((id) => !PANEL_REHBERI[id]);
    expect(eksik, `bu panellerin öğretici rehberi yok: ${eksik.join(', ')}`).toEqual([]);

    // Ters yön: rehberi olup paneli olmayan kayıt — ölü içerik birikmesin
    const fazla = Object.keys(PANEL_REHBERI).filter((k) => !idler.includes(k));
    expect(fazla, `bu rehberlerin paneli yok: ${fazla.join(', ')}`).toEqual([]);
  });

  it('sihirbaz doğrulama anahtarları backend rehberinin bildiği anahtarlar', () => {
    const kaynak = readFileSync(
      resolve(BURASI, '../../app/routers/onboarding.py'), 'utf-8');
    const blok = kaynak.match(/tamamlar = \{([\s\S]*?)\n    \}/);
    expect(blok, 'onboarding.py içinde `tamamlar` sözlüğü bulunamadı').toBeTruthy();

    const backendAnahtarlari = [...blok[1].matchAll(/"([a-z_]+)":/g)].map((m) => m[1]);
    expect(backendAnahtarlari).toContain('hesap');

    const kullanilan = SIHIRBAZ_ADIMLARI
      .map((a) => a.dogrulamaAnahtari)
      .filter(Boolean);
    const tanimsiz = kullanilan.filter((k) => !backendAnahtarlari.includes(k));
    expect(tanimsiz,
      `sihirbaz backend'in bilmediği anahtara bakıyor: ${tanimsiz.join(', ')}`).toEqual([]);
  });

  it('her rehber gerçekten öğretiyor — özet, adımlar ve örnek dolu', () => {
    for (const [id, r] of Object.entries(PANEL_REHBERI)) {
      expect(r.ozet?.length, `${id}: özet yok`).toBeGreaterThan(20);
      expect(r.nasil?.length, `${id}: nasıl kullanılır adımı yok`).toBeGreaterThan(1);
      expect(r.ornek?.length, `${id}: örnek yok`).toBeGreaterThan(10);
    }
    // Sihirbazın yönlendiren adımlarının örneği olmalı — örneksiz "şunu yap" öğretmez
    for (const a of SIHIRBAZ_ADIMLARI.filter((x) => x.hedefSekme)) {
      expect(a.ornek?.length, `${a.id}: yönlendiren adımın örneği yok`).toBeGreaterThan(5);
    }
  });

  it('bilinmeyen sekme için rehber null (bileşen çizmez, çökmez)', () => {
    expect(panelRehberi('boyle_bir_panel_yok')).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════
// 2 — İPUCU ŞERİDİ
// ══════════════════════════════════════════════════════════════════════

describe('Ipucu', () => {
  it('özeti gösterir, detayı ancak istenince açar', () => {
    render(<Ipucu sekme="accounts" />);
    expect(screen.getByText(PANEL_REHBERI.accounts.ozet)).toBeInTheDocument();

    // Detay kapalıyken örnek görünmemeli — şerit ekranı işgal etmesin
    expect(screen.queryByText('Örnek')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /nasıl kullanılır/i }));
    expect(screen.getByText('Örnek')).toBeInTheDocument();
    expect(screen.getByText(PANEL_REHBERI.accounts.ornek)).toBeInTheDocument();
    expect(screen.getByText(PANEL_REHBERI.accounts.nasil[0])).toBeInTheDocument();
  });

  it('kapatılınca kaybolur ve bir daha açılışta gelmez', () => {
    const { unmount } = render(<Ipucu sekme="budget" />);
    fireEvent.click(screen.getByRole('button', { name: 'İpucunu gizle' }));
    expect(screen.queryByText(PANEL_REHBERI.budget.ozet)).not.toBeInTheDocument();

    unmount();
    render(<Ipucu sekme="budget" />);
    expect(screen.queryByText(PANEL_REHBERI.budget.ozet)).not.toBeInTheDocument();
  });

  it('bir panelin gizlenmesi diğerini gizlemez', () => {
    render(<Ipucu sekme="budget" />);
    fireEvent.click(screen.getByRole('button', { name: 'İpucunu gizle' }));

    render(<Ipucu sekme="goals" />);
    expect(screen.getByText(PANEL_REHBERI.goals.ozet)).toBeInTheDocument();
  });

  it('bilinmeyen sekmede hiç çizilmez', () => {
    const { container } = render(<Ipucu sekme="yok_boyle" />);
    expect(container.firstChild).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════
// 3 — KURULUM SİHİRBAZI
// ══════════════════════════════════════════════════════════════════════

describe('OgreticiSihirbaz', () => {
  it('adımlar arasında ilerler ve örneği gösterir', async () => {
    stubFetch(REHBER);
    render(<OgreticiSihirbaz onKapat={() => {}} setActiveTab={() => {}} />);

    expect(screen.getByText(SIHIRBAZ_ADIMLARI[0].baslik)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /devam|sonra/i }));

    const ikinci = SIHIRBAZ_ADIMLARI[1];
    expect(screen.getByText(ikinci.baslik)).toBeInTheDocument();
    expect(screen.getByText(ikinci.ornek.split(String.fromCharCode(10))[0], { exact: false })).toBeInTheDocument();
  });

  it('"Şimdi yap" hedef panele götürür ve sihirbazı kapatır', () => {
    stubFetch(REHBER);
    const gitti = [];
    const kapandi = vi.fn();
    render(<OgreticiSihirbaz onKapat={kapandi} setActiveTab={(t) => gitti.push(t)} />);

    fireEvent.click(screen.getByRole('button', { name: /devam|sonra/i }));   // hesap adımı
    fireEvent.click(screen.getByRole('button', { name: /şimdi yap/i }));

    expect(gitti).toEqual([SIHIRBAZ_ADIMLARI[1].hedefSekme]);
    expect(kapandi).toHaveBeenCalled();
  });

  it('tamamlanmış adımı backend verisinden okur — kendi sayacını tutmaz', async () => {
    stubFetch(REHBER);   // 'hesap' tamam
    render(<OgreticiSihirbaz onKapat={() => {}} setActiveTab={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: /devam|sonra/i }));
    await waitFor(() => {
      expect(screen.getByText(/bu adımı zaten tamamladın/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /sonra|devam/i }));   // islem: tamam DEĞİL
    expect(screen.queryByText(/bu adımı zaten tamamladın/i)).not.toBeInTheDocument();
  });

  it('bitirince rehberi gizler (PATCH) ve kapanır', async () => {
    const cagrilar = [];
    vi.stubGlobal('fetch', vi.fn(async (url, opts) => {
      cagrilar.push({ yol: new URL(url, 'http://localhost').pathname, method: opts?.method || 'GET' });
      return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => REHBER };
    }));
    const kapandi = vi.fn();
    render(<OgreticiSihirbaz onKapat={kapandi} setActiveTab={() => {}}
                             baslangicAdimi={SIHIRBAZ_ADIMLARI.length - 1} />);

    fireEvent.click(screen.getByRole('button', { name: /bitir/i }));
    await waitFor(() => expect(kapandi).toHaveBeenCalled());
    expect(cagrilar.some((c) => c.method === 'PATCH' && c.yol.endsWith('/rehber'))).toBe(true);
  });

  it('rehber okunamasa bile açılır ve kapanabilir (yardım, hataya bağlı olamaz)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('ağ yok'); }));
    const kapandi = vi.fn();
    render(<OgreticiSihirbaz onKapat={kapandi} setActiveTab={() => {}} />);

    expect(screen.getByText(SIHIRBAZ_ADIMLARI[0].baslik)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /sihirbazı kapat/i }));
    expect(kapandi).toHaveBeenCalled();
  });
});

// ══════════════════════════════════════════════════════════════════════
// 4 — YARDIM KÖŞESİ
// ══════════════════════════════════════════════════════════════════════

describe('YardimKosesi', () => {
  it('kapalıyken yalnız düğme durur; açılınca aktif panelin özetini verir', () => {
    render(<YardimKosesi sekme="cashflow" onSihirbaz={() => {}} />);
    expect(screen.queryByText(PANEL_REHBERI.cashflow.ozet)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /yardıma mı ihtiyacın var/i }));
    expect(screen.getByText(PANEL_REHBERI.cashflow.ozet)).toBeInTheDocument();
    expect(screen.getByText(PANEL_REHBERI.cashflow.baslik)).toBeInTheDocument();
  });

  it('sihirbazı yeniden başlatır', () => {
    const sihirbaz = vi.fn();
    render(<YardimKosesi sekme="cockpit" onSihirbaz={sihirbaz} />);
    fireEvent.click(screen.getByRole('button', { name: /yardıma mı ihtiyacın var/i }));
    fireEvent.click(screen.getByRole('button', { name: /kurulum sihirbazı/i }));
    expect(sihirbaz).toHaveBeenCalled();
  });

  it('verilmeyen seçenek menüde görünmez', () => {
    render(<YardimKosesi sekme="cockpit" onSihirbaz={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /yardıma mı ihtiyacın var/i }));
    expect(screen.queryByRole('button', { name: /klavye kısayolları/i })).not.toBeInTheDocument();
  });

  it('her panelde çizilir — rehberi olmayan sekmede bile düğme kalır', () => {
    render(<YardimKosesi sekme="tanimsiz" onSihirbaz={() => {}} />);
    expect(screen.getByRole('button', { name: /yardıma mı ihtiyacın var/i })).toBeInTheDocument();
  });
});
