import { useState, useEffect, useCallback } from 'react';
import { Loader2, Plus, ShoppingBag, Check, X, Clock } from 'lucide-react';
import { wishlistApi, formatTL, parseTRNumber } from '../api';
import { useToast } from './Toast.jsx';
import { formatPara } from '../lib/money.js';

/**
 * FEAT-032: İstek listesi / 24-saat impuls bekleme. Büyük/plansız alımı hemen yapmak yerine
 * listeye ekle; 24 saat sonra "hâlâ istiyor musun?" (kart borcu dururken bu tutar faize döner).
 * İmpuls harcamayı kırar — borç-batık için doğrudan davranışsal lever.
 */
export default function Wishlist() {
  const toast = useToast();
  const [data, setData] = useState(null);   // {items, bekleyen_adet, review_adet}
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ item: '', amount: '' });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setData(await wishlistApi.list());
    } catch (e) {
      toast.error(e.message || 'İstek listesi yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const add = async (e) => {
    e.preventDefault();
    const amount = parseTRNumber(form.amount); // W3-001
    if (!form.item.trim() || !(amount > 0)) { toast.error('Ürün ve geçerli tutar gir.'); return; }
    try {
      setSaving(true);
      await wishlistApi.add({ item: form.item.trim(), amount });
      setForm({ item: '', amount: '' });
      load();
    } catch (e2) { toast.error(`Eklenemedi: ${e2.message}`); }
    finally { setSaving(false); }
  };

  const resolve = async (id, status) => {
    try {
      await wishlistApi.resolve(id, status);
      load();
    } catch (e) { toast.error(`Güncellenemedi: ${e.message}`); }
  };

  const items = data?.items ?? [];

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <ShoppingBag className="w-5 h-5 text-brand-600 dark:text-brand-400" />
        <h3 className="font-semibold text-zinc-800 dark:text-zinc-100">İstek Listesi</h3>
        {data?.review_adet > 0 && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-warn-100 dark:bg-warn-900/40 text-warn-700 dark:text-warn-300">
            {data.review_adet} gözden geçir
          </span>
        )}
      </div>
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Büyük bir alımı hemen yapma — buraya ekle. 24 saat sonra hâlâ istiyorsan al; çoğu
        impuls o sürede geçer. Kart borcu dururken her ertelenen alım borcu hızlandırır.
      </p>

      <form onSubmit={add} className="flex flex-wrap gap-2 items-end">
        <input
          type="text" placeholder="Ne almak istiyorsun?" value={form.item}
          onChange={(e) => setForm((f) => ({ ...f, item: e.target.value }))}
          className="flex-1 min-w-[140px] rounded-md bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 px-2 py-1.5 text-sm text-zinc-900 dark:text-zinc-100"
        />
        <input
          type="number" step="0.01" min="0" placeholder="Tutar" value={form.amount}
          onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
          className="w-28 rounded-md bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 px-2 py-1.5 text-sm text-zinc-900 dark:text-zinc-100"
        />
        <button type="submit" disabled={saving} className="btn btn-secondary !text-xs">
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
          Ekle
        </button>
      </form>

      {loading ? (
        <div className="text-sm text-zinc-400 flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Yükleniyor…</div>
      ) : items.length === 0 ? (
        <p className="text-sm text-zinc-400">Liste boş. İmpuls bir alım geldiğinde buraya ekle.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((w) => (
            <li key={w.id} className={`flex items-center gap-2 text-sm rounded-md px-2 py-1.5 ${
              w.hazir ? 'bg-warn-50 dark:bg-warn-950/30' : 'bg-zinc-50 dark:bg-zinc-800/50'
            }`}>
              <div className="flex-1 min-w-0">
                <span className="text-zinc-800 dark:text-zinc-100">{w.item}</span>
                <span className="text-zinc-400 dark:text-zinc-500"> · {formatPara(w.amount)}</span>
                {w.hazir && (
                  <span className="ml-1 inline-flex items-center gap-0.5 text-xs text-warn-600 dark:text-warn-400">
                    <Clock className="w-3 h-3" /> 24s doldu
                  </span>
                )}
              </div>
              <button type="button" onClick={() => resolve(w.id, 'bought')} title="Aldım"
                className="p-1 rounded text-positive-600 dark:text-positive-400 hover:bg-positive-50 dark:hover:bg-positive-900/30">
                <Check className="w-4 h-4" />
              </button>
              <button type="button" onClick={() => resolve(w.id, 'dismissed')} title="Vazgeçtim"
                className="p-1 rounded text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-700">
                <X className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}