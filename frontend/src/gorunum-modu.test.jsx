/**
 * GÖRÜNÜM MODU KAPISI — "sadeleştirme, bilgi eksiltmek değildir" sözleşmesi.
 *
 * Dönen bir kullanıcının geri bildirimi tekti: "anlaması çok zor, çok detay var".
 * Cevap, detayı SİLMEK değil SEÇİLİR yapmak oldu. Ama seçilir yapmanın kolay yolu —
 * "az göster, gerisini yut" — daha kötüsünü üretir: kullanıcı neyi kaçırdığını
 * bilmez, çünkü kayıp görünmez. Bu dosya o kolay yolu kapatır.
 *
 * Kilitlenen değişmezler:
 *   1. Tercih SORULUR: hiç seçim yokken `okuModu()` null döner (varsayılan ≠ seçim).
 *      Seçim yapıldıktan sonra soru bir daha sorulmaz.
 *   2. Seçim İKİ YÖNLÜDÜR ve kalıcıdır; Hesap panelindeki anahtar her iki yöne çalışır.
 *   3. Sade görünümde sekmeler AZALIR ama hiçbir panel YOK OLMAZ: sade sekme kümesi
 *      tam kümenin alt kümesidir ve tüm paneller komut paletinde durur.
 *   4. Klavye kısayolları GÖRÜNEN sekmelere bağlanır — kullanıcıyı çubukta olmayan
 *      bir panele ışınlayan kısayol, aktif sekmesi görünmeyen bir arayüz bırakır.
 *   5. Komut paleti her iki modda da 13 panelin TAMAMINI listeler (eski hâlde "Aile"
 *      ve "Hesap" hiç yoktu).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import {
  BASIT, DETAYLI, okuModu, etkinMod, yazModu, unutModu,
} from './lib/gorunumModu.js';
import { SEKMELER, gorunurSekmeler, sekmeEtiketi, kisayolSirasi } from './lib/sekmeler.js';
import GorunumSecici from './components/GorunumSecici.jsx';
import CommandPalette from './components/CommandPalette.jsx';

vi.mock('./api.js', () => ({
  ApiError: class ApiError extends Error {},
  clearTokens: vi.fn(),
  userApi: { get: vi.fn().mockResolvedValue({ name: 'Beta', email: 'beta@ornek.com' }) },
  authApi: {
    me: vi.fn().mockResolvedValue({ name: 'Beta', email: 'beta@ornek.com', has_password: true }),
    changeEmail: vi.fn().mockResolvedValue({}),
    changePassword: vi.fn().mockResolvedValue({}),
    exportData: vi.fn().mockResolvedValue({}),
    deleteMe: vi.fn().mockResolvedValue(null),
  },
  onboardingApi: {
    rehber: vi.fn().mockResolvedValue({
      adimlar: [], tamamlanan: 1, toplam: 4, tamamlandi: true, gizli: false, gorunur: false,
    }),
    rehberGizle: vi.fn().mockResolvedValue({}),
  },
}));

// eslint-disable-next-line import/first
import Hesap from './panels/Hesap.jsx';

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

// ══════════════════════════════════════════════════════════════════════
// 1 — TERCİH: varsayılan bir seçim DEĞİLDİR
// ══════════════════════════════════════════════════════════════════════

describe('tercih', () => {
  it('hiç seçim yapılmamışsa okuModu null döner — soru sorulacak demektir', () => {
    expect(okuModu()).toBeNull();
  });

  it('seçim yokken çizim sade görünümle yapılır (yeni kullanıcı duvara çarpmasın)', () => {
    expect(etkinMod(null)).toBe(BASIT);
  });

  it('seçim kaydedilir ve okunur; çöp değer seçilmemiş sayılır', () => {
    yazModu(DETAYLI);
    expect(okuModu()).toBe(DETAYLI);
    localStorage.setItem('fos_gorunum_modu', 'uzay-modu');
    expect(okuModu()).toBeNull();
    expect(etkinMod(okuModu())).toBe(BASIT);
  });

  it('mod değişimi AYNI sekmedeki dinleyicilere duyurulur', () => {
    const dinleyici = vi.fn();
    window.addEventListener('fos:gorunum-modu', dinleyici);
    yazModu(DETAYLI);
    expect(dinleyici).toHaveBeenCalledTimes(1);
    window.removeEventListener('fos:gorunum-modu', dinleyici);
  });

  it('unutModu tercihi siler — soru yeniden sorulabilir hâle gelir', () => {
    yazModu(BASIT);
    unutModu();
    expect(okuModu()).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════
// 2 — SEKMELER: azalır ama kaybolmaz
// ══════════════════════════════════════════════════════════════════════

describe('sekme kümesi', () => {
  it('sade küme tam kümenin ALT KÜMESİDİR — sade görünüm panel uydurmaz', () => {
    const tumIdler = SEKMELER.map((s) => s.id);
    const sadeIdler = gorunurSekmeler(true).map((s) => s.id);
    expect(sadeIdler.every((id) => tumIdler.includes(id))).toBe(true);
  });

  it('sade görünüm gerçekten sadeleştirir ama ekranı boşaltmaz', () => {
    const sade = gorunurSekmeler(true);
    const tum = gorunurSekmeler(false);
    expect(sade.length).toBeLessThan(tum.length);
    expect(sade.length).toBeGreaterThanOrEqual(4);
  });

  it('günlük kararın panelleri sade görünümde durur', () => {
    const sadeIdler = gorunurSekmeler(true).map((s) => s.id);
    // Özet: bugün ne kadar harcarım · Hesaplar: param nerede · İşlemler: ne harcadım
    // Koç: soru sorabileceğim yer · Hesap: görünümü geri alabileceğim yer
    for (const id of ['cockpit', 'accounts', 'transactions', 'coach', 'hesap']) {
      expect(sadeIdler, `sade görünümde ${id} olmalı`).toContain(id);
    }
  });

  it('Cockpit sade görünümde anlaşılır bir ad taşır', () => {
    const cockpit = SEKMELER.find((s) => s.id === 'cockpit');
    expect(sekmeEtiketi(cockpit, true)).toBe('Özet');
    expect(sekmeEtiketi(cockpit, false)).toBe('Cockpit');
  });

  it('klavye kısayolları yalnız GÖRÜNEN sekmelere bağlanır', () => {
    expect(kisayolSirasi(true)).toEqual(gorunurSekmeler(true).map((s) => s.id));
    expect(kisayolSirasi(false)).toEqual(SEKMELER.map((s) => s.id));
  });
});

// ══════════════════════════════════════════════════════════════════════
// 3 — SORU EKRANI
// ══════════════════════════════════════════════════════════════════════

describe('GorunumSecici', () => {
  it('iki seçeneği de tarif eder ve seçim geri çağrısını verir', () => {
    const onSec = vi.fn();
    render(<GorunumSecici onSec={onSec} />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Detaylı/ }));
    expect(onSec).toHaveBeenCalledWith(DETAYLI);
  });

  it('Esc = karar veremedim: sade ile devam edilir, ekran kilitlenmez', () => {
    const onSec = vi.fn();
    render(<GorunumSecici onSec={onSec} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onSec).toHaveBeenCalledWith(BASIT);
  });

  it('kararın kalıcı olmadığı ekranda YAZILIDIR', () => {
    render(<GorunumSecici onSec={vi.fn()} />);
    expect(screen.getByText(/istediğin an değiştirirsin/i)).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════
// 4 — HESAP PANELİNDEKİ ANAHTAR: iki yönlü ve kalıcı
// ══════════════════════════════════════════════════════════════════════

describe('Hesap panelindeki görünüm anahtarı', () => {
  it('sadeden detaylıya ve geri dönüş — ikisi de tek tık', async () => {
    yazModu(BASIT);
    render(<Hesap />);

    const detayli = await screen.findByRole('button', { name: 'Detaylı' });
    const sade = screen.getByRole('button', { name: 'Sade' });
    expect(sade).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(detayli);
    await waitFor(() => expect(okuModu()).toBe(DETAYLI));
    expect(detayli).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(sade);
    await waitFor(() => expect(okuModu()).toBe(BASIT));
  });

  it('sade görünümde NEYİN gizlendiği panelde yazılıdır', async () => {
    yazModu(BASIT);
    render(<Hesap />);
    expect(await screen.findByText(/analiz bölümleri gizli/i)).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════
// 5 — KOMUT PALETİ: sade görünüm hiçbir paneli erişilemez bırakmaz
// ══════════════════════════════════════════════════════════════════════

describe('komut paleti', () => {
  it('sade görünümde de 13 panelin tamamı listelenir', () => {
    render(<CommandPalette onClose={vi.fn()} setActiveTab={vi.fn()} basit onModDegistir={vi.fn()} />);
    for (const s of SEKMELER) {
      expect(screen.getByText(s.komut), `palette ${s.id} yok`).toBeInTheDocument();
    }
  });

  it('görünümü değiştiren komut palette de vardır', () => {
    const onModDegistir = vi.fn();
    const onClose = vi.fn();
    render(<CommandPalette onClose={onClose} setActiveTab={vi.fn()} basit onModDegistir={onModDegistir} />);
    fireEvent.click(screen.getByText('Görünümü detaylıya çevir'));
    expect(onModDegistir).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('panel komutu sekmeyi değiştirir (Aile ve Hesap dahil — eskiden palette yoktular)', () => {
    const setActiveTab = vi.fn();
    render(<CommandPalette onClose={vi.fn()} setActiveTab={setActiveTab} />);
    fireEvent.click(screen.getByText('Aile\'ye geç'));
    expect(setActiveTab).toHaveBeenCalledWith('workspace');
  });
});
