import { useState, useEffect, useCallback } from 'react';
import { Loader2, Plus, Trash2, Wallet } from 'lucide-react';
import { envelopesApi, formatTL, parseTRNumber } from '../api';
import { useToast } from '../components/Toast.jsx';
import DetectedSubscriptions from '../components/DetectedSubscriptions.jsx';
import Wishlist from '../components/Wishlist.jsx';
import { formatPara, formatSayi, paraEtiketi } from '../lib/money.js';

/**
 * Bütçe Zarfları (FEAT-001) — kategori bazlı aylık bütçe. Her zarf: bütçe / bu-ay harcanan /
 * kalan + ilerleme çubuğu (aşıldıysa kırmızı). Ekle / sil.
 *
 * GUNCELLEMELER
 *  - BUG #219 fix (P3.2): yukleme hatasi yalnizca toast'a dusuyor, `data` null kaliyordu;
 *    render `data.envelopes.length` okudugu icin panel COKUYORDU (ErrorBoundary devreye
 *    girer). Ayni dosyada `data?.durum` guard'liydi — tutarsizlik bug'in kendisiydi.
 *    Artik hata state'te tutulur, ekranda kalici hata karti + "Tekrar dene" gosterilir
 *    (yukleme basarisizken kullaniciya "zarfin yok" DENMEZ).
 */
export default function Budget() {
  const toast = useToast();
  const [data, setData] = useState(null);      // {envelopes, durum}
  const [hata, setHata] = useState(null);      // BUG #219: yükleme hatası ekranda kalır
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ category: '', monthly_amount: '' });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setData(await envelopesApi.list());
      setHata(null);  // BUG #219
    } catch (e) {
      // BUG #219 fix: hata yalnız toast'a düşüyordu, `data` null kalıyordu ve aşağıda
      // `data.envelopes` okunduğu için panel ÇÖKÜYORDU (toast 4 sn sonra kaybolur,
      // geriye sebepsiz boş/kırık ekran kalırdı). Hata artık ekranda kalıcı + tekrar denenebilir.
      setHata(e.message || 'Zarflar yüklenemedi');
      toast.error(e.message || 'Zarflar yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const add = async (e) => {
    e.preventDefault();
    if (!form.category.trim() || !(parseTRNumber(form.monthly_amount) > 0)) return; // W3-001
    try {
      setSaving(true);
      await envelopesApi.create({
        category: form.category.trim().toLowerCase(),
        monthly_amount: parseTRNumber(form.monthly_amount), // W3-001
      });
      setForm({ category: '', monthly_amount: '' });
      toast.success('Zarf eklendi');
      load();
    } catch (e) {
      toast.error(e.message || 'Eklenemedi');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    try {
      await envelopesApi.delete(id);
      toast.success('Zarf silindi');
      load();
    } catch (e) {
      toast.error(e.message || 'Silinemedi');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-zinc-500">
        <Loader2 className="w-6 h-6 animate-spin mr-2" /> Yükleniyor...
      </div>
    );
  }

  // BUG #219: yükleme başarısızsa "zarfın yok" DEME — veriyi bilmiyoruz. Ayrı ekran.
  if (hata) {
    return (
      <div className="card p-6 text-center space-y-3">
        <p className="text-sm text-negative-600 dark:text-negative-400">Bütçe zarfları yüklenemedi.</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{hata}</p>
        <button type="button" onClick={load} className="btn btn-secondary">Tekrar dene</button>
      </div>
    );
  }

  const durum = data?.durum || { zarflar: [], toplam_butce: 0, toplam_harcanan: 0, toplam_kalan: 0 };
  const statusByCat = Object.fromEntries((durum.zarflar || []).map((z) => [z.category, z]));
  const zarflar = data?.envelopes || [];  // BUG #219: `data` null olabilir (hata yolu)

  return (
    <div className="space-y-4">
      {/* Ready to Assign (FEAT-002) — YNAB "her liraya görev" */}
      {data?.atanmamis_nakit !== undefined && (
        <div className="card p-4 border-brand-200 dark:border-brand-800/50 bg-brand-50/50 dark:bg-brand-950/20">
          <p className="text-xs text-zinc-600 dark:text-zinc-400">Boşta nakit (henüz zarfa atanmamış)</p>
          <p className={`font-numeric text-2xl font-bold ${data.atanmamis_nakit < 0 ? 'text-negative-600 dark:text-negative-400' : 'text-brand-700 dark:text-brand-400'}`}>
            {formatPara(data.atanmamis_nakit)}
          </p>
          {data.atanmamis_nakit < 0 && (
            <p className="text-xs text-negative-600 dark:text-negative-400 mt-0.5">Aşırı bütçeleme — nakdinden fazlasını zarflara ayırdın.</p>
          )}
        </div>
      )}

      {/* Özet */}
      <div className="card p-4 flex items-center gap-3">
        <Wallet className="w-5 h-5 text-brand-600 dark:text-brand-400" />
        <div className="text-sm">
          <span className="font-semibold">{formatPara(durum.toplam_butce)}</span> bütçe ·{' '}
          <span className="font-numeric">{formatPara(durum.toplam_harcanan)}</span> harcandı ·{' '}
          <span className={durum.toplam_kalan < 0 ? 'text-negative-600 dark:text-negative-400' : 'text-positive-600 dark:text-positive-400'}>
            {formatPara(durum.toplam_kalan)} kaldı
          </span>
        </div>
      </div>

      {/* Yeni zarf */}
      <form onSubmit={add} className="card p-4 flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-[140px]">
          <label className="text-xs text-zinc-500 dark:text-zinc-400">Kategori</label>
          <input className="input w-full" placeholder="market, yemek, eğlence..."
                 value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
        </div>
        <div className="w-32">
          <label className="text-xs text-zinc-500 dark:text-zinc-400">Aylık bütçe ({paraEtiketi()})</label>
          <input type="number" min="1" step="1" className="input w-full" placeholder="2000"
                 value={form.monthly_amount} onChange={(e) => setForm({ ...form, monthly_amount: e.target.value })} />
        </div>
        <button type="submit" disabled={saving} className="btn btn-primary flex items-center gap-1">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Ekle
        </button>
      </form>

      {/* Zarf listesi */}
      {zarflar.length === 0 ? (
        <p className="text-center text-sm text-zinc-500 py-8">
          Henüz bütçe zarfı yok. Bir kategoriye aylık bütçe ekle — harcaman otomatik düşülür.
        </p>
      ) : (
        <div className="space-y-2">
          {zarflar.map((env) => {
            const st = statusByCat[env.category] || { harcanan: 0, butce: parseFloat(env.monthly_amount), kalan: parseFloat(env.monthly_amount), yuzde: 0, asildi: false };
            const pct = Math.min(100, st.yuzde || 0);
            return (
              <div key={env.id} className="card p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-medium capitalize">{env.category}</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-numeric ${st.asildi ? 'text-negative-600 dark:text-negative-400' : 'text-zinc-600 dark:text-zinc-300'}`}>
                      {formatSayi(st.harcanan)} / {formatPara(st.butce)}
                    </span>
                    <button type="button" onClick={() => remove(env.id)} className="text-zinc-400 hover:text-negative-500 min-w-[44px] min-h-[44px] inline-flex items-center justify-center shrink-0 -my-2" title="Sil">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="h-2 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
                  <div className={`h-full rounded-full ${st.asildi ? 'bg-negative-500' : pct > 80 ? 'bg-warn-500' : 'bg-positive-500'}`}
                       style={{ width: `${pct}%` }} />
                </div>
                <p className={`text-xs mt-1 ${st.asildi ? 'text-negative-600 dark:text-negative-400' : 'text-zinc-500 dark:text-zinc-400'}`}>
                  {st.asildi ? `${formatPara(-st.kalan)} aşıldı` : `${formatPara(st.kalan)} kaldı`}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {/* FEAT-006: tespit edilen abonelikler + düzenli gidere çevir */}
      <DetectedSubscriptions />

      {/* FEAT-032: istek listesi / 24-saat impuls bekleme */}
      <Wishlist />
    </div>
  );
}