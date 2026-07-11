import { useState, useEffect, useCallback } from 'react';
import { Loader2, Plus, Trash2, Wallet } from 'lucide-react';
import { envelopesApi, formatTL } from '../api';
import { useToast } from '../components/Toast.jsx';

/**
 * Bütçe Zarfları (FEAT-001) — kategori bazlı aylık bütçe. Her zarf: bütçe / bu-ay harcanan /
 * kalan + ilerleme çubuğu (aşıldıysa kırmızı). Ekle / sil.
 */
export default function Budget() {
  const toast = useToast();
  const [data, setData] = useState(null);      // {envelopes, durum}
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ category: '', monthly_amount: '' });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setData(await envelopesApi.list());
    } catch (e) {
      toast.error(e.message || 'Zarflar yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const add = async (e) => {
    e.preventDefault();
    if (!form.category.trim() || !(parseFloat(form.monthly_amount) > 0)) return;
    try {
      setSaving(true);
      await envelopesApi.create({
        category: form.category.trim().toLowerCase(),
        monthly_amount: parseFloat(form.monthly_amount),
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

  const durum = data?.durum || { zarflar: [], toplam_butce: 0, toplam_harcanan: 0, toplam_kalan: 0 };
  const statusByCat = Object.fromEntries((durum.zarflar || []).map((z) => [z.category, z]));

  return (
    <div className="space-y-4">
      {/* Özet */}
      <div className="card p-4 flex items-center gap-3">
        <Wallet className="w-5 h-5 text-brand-600 dark:text-brand-400" />
        <div className="text-sm">
          <span className="font-semibold">{formatTL(durum.toplam_butce)} TL</span> bütçe ·{' '}
          <span className="font-numeric">{formatTL(durum.toplam_harcanan)} TL</span> harcandı ·{' '}
          <span className={durum.toplam_kalan < 0 ? 'text-negative-600 dark:text-negative-400' : 'text-positive-600 dark:text-positive-400'}>
            {formatTL(durum.toplam_kalan)} TL kaldı
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
          <label className="text-xs text-zinc-500 dark:text-zinc-400">Aylık bütçe (TL)</label>
          <input type="number" min="1" step="1" className="input w-full" placeholder="2000"
                 value={form.monthly_amount} onChange={(e) => setForm({ ...form, monthly_amount: e.target.value })} />
        </div>
        <button type="submit" disabled={saving} className="btn btn-primary flex items-center gap-1">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Ekle
        </button>
      </form>

      {/* Zarf listesi */}
      {data.envelopes.length === 0 ? (
        <p className="text-center text-sm text-zinc-500 py-8">
          Henüz bütçe zarfı yok. Bir kategoriye aylık bütçe ekle — harcaman otomatik düşülür.
        </p>
      ) : (
        <div className="space-y-2">
          {data.envelopes.map((env) => {
            const st = statusByCat[env.category] || { harcanan: 0, butce: parseFloat(env.monthly_amount), kalan: parseFloat(env.monthly_amount), yuzde: 0, asildi: false };
            const pct = Math.min(100, st.yuzde || 0);
            return (
              <div key={env.id} className="card p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-medium capitalize">{env.category}</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-numeric ${st.asildi ? 'text-negative-600 dark:text-negative-400' : 'text-zinc-600 dark:text-zinc-300'}`}>
                      {formatTL(st.harcanan)} / {formatTL(st.butce)} TL
                    </span>
                    <button onClick={() => remove(env.id)} className="text-zinc-400 hover:text-negative-500" title="Sil">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="h-2 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
                  <div className={`h-full rounded-full ${st.asildi ? 'bg-negative-500' : pct > 80 ? 'bg-warn-500' : 'bg-positive-500'}`}
                       style={{ width: `${pct}%` }} />
                </div>
                <p className={`text-xs mt-1 ${st.asildi ? 'text-negative-600 dark:text-negative-400' : 'text-zinc-500 dark:text-zinc-400'}`}>
                  {st.asildi ? `${formatTL(-st.kalan)} TL aşıldı` : `${formatTL(st.kalan)} TL kaldı`}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
